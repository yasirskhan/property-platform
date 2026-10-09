"""Yardi file staging through the existing platform migration metadata.

No customer-side record or source relationship is created by an upload.
Yardi schemas differ by export/interface, so source-to-target columns must
be explicitly mapped rather than inferred from AppFolio column conventions.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.platform_migration import (
    PlatformMigrationItem, PlatformMigrationRun, PlatformMigrationStagedRow,
    PlatformMigrationUpload,
)
from app.models.property import Property
from app.services.appfolio_file_ingestion import (
    AppFolioFileIngestionError, StagedUploadResult, _clean_cell, _fingerprint,
    _mapped_value, _normalize_header, _parse_file, _row_fingerprint,
    _safe_filename, PROPERTY_REQUIRED,
)

PROPERTY_FIELDS = frozenset((
    "source_id", "name", "address_line1", "address_line2",
    "city", "state", "zip_code", "property_type",
))


def stage_yardi_file(
    db: Session, *, run: PlatformMigrationRun, filename: str,
    content: bytes, resource_override: str | None, sheet_name: str | None,
    explicit_mapping: dict[str, str] | None, platform_user_id: int,
) -> StagedUploadResult:
    if run.provider != "YARDI":
        raise AppFolioFileIngestionError("Migration run is not a Yardi run.")
    if (resource_override or "").strip().upper() != "PROPERTIES":
        raise AppFolioFileIngestionError(
            "Choose resource PROPERTIES; other Yardi resources require verified source contracts."
        )
    filename = _safe_filename(filename)
    parsed = _parse_file(filename, content, sheet_name)
    mapping = explicit_mapping or {}
    if not isinstance(mapping, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in mapping.items()
    ):
        raise AppFolioFileIngestionError("Column mapping must contain string fields and headers.")
    if set(mapping) - PROPERTY_FIELDS:
        raise AppFolioFileIngestionError("Unknown Yardi property mapping field.")
    if len(set(mapping.values())) != len(mapping):
        raise AppFolioFileIngestionError("Each source column may map to only one field.")
    if any(header not in parsed.headers for header in mapping.values()):
        raise AppFolioFileIngestionError("Column mapping references an unknown source header.")
    missing = sorted(set(PROPERTY_REQUIRED) - set(mapping))
    # Preserve unambiguous manual mappings, but block incomplete source contracts.
    canonical = {
        "provider": "YARDI", "organization_id": run.organization_id,
        "source_account_ref": run.source_account_ref,
        "resource": "PROPERTIES", "sheet_name": parsed.sheet_name,
        "mapping": {k: _normalize_header(v) for k, v in sorted(mapping.items())},
        "rows": [{"row_number": n, "data": {
            _normalize_header(k): _clean_cell(v) for k, v in row.items()
        }} for n, row in parsed.rows],
    }
    fingerprint = hashlib.sha256(json.dumps(
        canonical, sort_keys=True, separators=(",", ":"), default=str,
    ).encode("utf-8")).hexdigest()
    existing = db.query(PlatformMigrationUpload).filter(
        PlatformMigrationUpload.run_id == run.id,
        PlatformMigrationUpload.organization_id == run.organization_id,
        PlatformMigrationUpload.provider == "YARDI",
        PlatformMigrationUpload.normalized_fingerprint == fingerprint,
    ).first()
    if existing:
        return StagedUploadResult(upload=existing, replayed=True)

    upload = PlatformMigrationUpload(
        run_id=run.id, organization_id=run.organization_id,
        provider="YARDI", filename=filename,
        file_format=parsed.file_format,
        file_sha256=hashlib.sha256(content).hexdigest(),
        normalized_fingerprint=fingerprint,
        detected_resource="PROPERTIES", sheet_name=parsed.sheet_name,
        headers=parsed.headers, column_mapping=mapping,
        validation_summary={}, status="STAGING",
        row_count=len(parsed.rows),
        created_by_platform_user_id=platform_user_id,
    )
    db.add(upload)
    db.flush()
    seen: set[str] = set()
    invalid = duplicates = matches = valid = 0
    for row_number, source in parsed.rows:
        data: dict[str, Any] = {
            field: _mapped_value(source, mapping, field)
            for field in PROPERTY_FIELDS if field in mapping
        }
        errors = [f"Missing required source column: {field}" for field in missing]
        for field in PROPERTY_REQUIRED:
            if not data.get(field) or not str(data[field]).strip():
                errors.append(f"{field} is required.")
        source_id = str(data.get("source_id") or "").strip() or None
        if source_id is not None:
            if source_id in seen:
                errors.append("Duplicate Yardi source ID within this upload.")
                duplicates += 1
            else:
                seen.add(source_id)
        disposition = "INVALID" if errors else "REVIEW"
        warnings: list[str] = []
        if errors:
            invalid += 1
        else:
            valid += 1
            mapped = db.query(PlatformMigrationItem).filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "YARDI",
                PlatformMigrationItem.resource == "PROPERTIES",
                PlatformMigrationItem.source_id == source_id,
            ).first()
            if mapped:
                disposition = "ALREADY_MAPPED"
                warnings.append("Source identity is already mapped; review before action.")
            else:
                possible = db.query(Property.id).filter(
                    Property.organization_id == run.organization_id,
                    Property.name == data.get("name"),
                    Property.address_line1 == data.get("address_line1"),
                    Property.city == data.get("city"),
                    Property.state == data.get("state"),
                    Property.zip_code == data.get("zip_code"),
                ).first()
                if possible:
                    matches += 1
                    disposition = "POSSIBLE_MATCH"
                    warnings.append("A possible target property exists; explicit review required.")
                else:
                    disposition = "REVIEW"
                    warnings.append("Yardi property source contract requires review before import.")
        db.add(PlatformMigrationStagedRow(
            upload_id=upload.id, run_id=run.id,
            organization_id=run.organization_id, provider="YARDI",
            resource="PROPERTIES", row_number=row_number,
            source_id=source_id, disposition=disposition,
            row_fingerprint=_row_fingerprint(source),
            normalized_data=data, warnings=warnings, errors=errors,
        ))
    upload.validation_summary = {
        "total": len(parsed.rows), "valid": valid, "invalid": invalid,
        "duplicates": duplicates, "possible_existing_matches": matches,
        "missing_required_columns": missing,
        "target_mutation": False, "requires_explicit_review": True,
    }
    upload.status = "MAPPING_REQUIRED" if missing else (
        "STAGED_WITH_ERRORS" if invalid else "REVIEW_REQUIRED"
    )
    run.last_dry_run_fingerprint = None
    run.last_dry_run_summary = None
    run.status = "STAGED"
    db.flush()
    return StagedUploadResult(upload=upload, replayed=False)
