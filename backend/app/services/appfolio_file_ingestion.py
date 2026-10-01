"""CSV/XLSX staging foundation for Phase 4.13 AppFolio migrations.

Files are parsed as data only. Raw bytes are never persisted, spreadsheet
formulas/macros are never executed, and staging never creates customer business
records. All persisted rows remain tied to the existing PlatformMigrationRun.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.platform_migration import (
    PlatformMigrationItem,
    PlatformMigrationRun,
    PlatformMigrationStagedRow,
    PlatformMigrationUpload,
)
from app.models.property import Property, Unit

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_ROWS = 10_000
MAX_COLUMNS = 100
MAX_SHEETS = 10
MAX_XLSX_ENTRIES = 2_000
MAX_XLSX_UNCOMPRESSED_BYTES = 64 * 1024 * 1024

SECRET_HEADER_KEYS = {
    "apikey",
    "clientsecret",
    "accesstoken",
    "refreshtoken",
    "authorization",
    "cookie",
    "password",
    "sessioncookie",
}

PROPERTY_ALIASES: dict[str, tuple[str, ...]] = {
    "source_id": ("Id", "Property Id", "PropertyId"),
    "name": ("Name", "Property Name"),
    "address_line1": ("Address1", "Address 1", "Street", "Street Address"),
    "address_line2": ("Address2", "Address 2", "Street 2"),
    "city": ("City",),
    "state": ("State", "Province"),
    "zip_code": ("Zip", "ZipCode", "Zip Code", "PostalCode", "Postal Code"),
    "property_type": ("PropertyType", "Property Type", "Type"),
    "hidden_at": ("HiddenAt", "Hidden At"),
}
PROPERTY_REQUIRED = (
    "source_id",
    "name",
    "address_line1",
    "city",
    "state",
    "zip_code",
)

# Verified Unit Directory export columns. These aliases intentionally stay
# narrower than the target Unit model: staging must not invent AppFolio fields.
UNIT_ALIASES: dict[str, tuple[str, ...]] = {
    "source_id": ("Unit ID", "Unit Id", "UnitID"),
    "source_property_id": ("Property ID", "Property Id", "PropertyID"),
    "unit_name": ("Unit Name", "Unit"),
    "property_name": ("Property Name", "Property"),
    "unit_address": ("Unit Address",),
    "address_line1": (
        "Unit Street Address 1",
        "Unit Address 1",
        "Unit Street 1",
    ),
    "address_line2": (
        "Unit Street Address 2",
        "Unit Address 2",
        "Unit Street 2",
    ),
    "city": ("Unit City",),
    "state": ("Unit State",),
    "zip_code": ("Unit Zip", "Unit Zip Code"),
}
# Unit Name is the only universally required display field in the verified
# export contract. Stable Unit/Property IDs are optional in AppFolio exports,
# but missing IDs remain REVIEW blockers for safe later commit.
UNIT_REQUIRED = ("unit_name",)


class AppFolioFileIngestionError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedTable:
    file_format: str
    sheet_name: str
    headers: list[str]
    rows: list[tuple[int, dict[str, Any]]]


@dataclass(frozen=True)
class StagedUploadResult:
    upload: PlatformMigrationUpload
    replayed: bool


def _normalize_header(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").strip().lower())


def _clean_cell(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip()
    return text or None


def _safe_filename(filename: str) -> str:
    name = Path(filename).name.strip()
    if not name or len(name) > 255:
        raise AppFolioFileIngestionError("Source filename is missing or too long.")
    return name


def _validate_headers(headers: list[str]) -> None:
    if not headers:
        raise AppFolioFileIngestionError("Source file has no header row.")
    if len(headers) > MAX_COLUMNS:
        raise AppFolioFileIngestionError(
            f"Source file exceeds the {MAX_COLUMNS}-column limit."
        )
    normalized = [_normalize_header(header) for header in headers]
    if any(not key for key in normalized):
        raise AppFolioFileIngestionError("Blank source headers are not supported.")
    if len(set(normalized)) != len(normalized):
        raise AppFolioFileIngestionError(
            "Duplicate or normalization-colliding source headers require cleanup before staging."
        )
    forbidden = sorted(set(normalized) & SECRET_HEADER_KEYS)
    if forbidden:
        raise AppFolioFileIngestionError(
            "Credential/session fields are not accepted in migration source files."
        )


def _parse_csv(content: bytes) -> ParsedTable:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise AppFolioFileIngestionError("CSV files must be UTF-8 encoded.") from exc
    reader = csv.reader(io.StringIO(text, newline=""))
    try:
        raw_headers = next(reader)
    except StopIteration as exc:
        raise AppFolioFileIngestionError("CSV file is empty.") from exc
    headers = [str(value).strip() for value in raw_headers]
    _validate_headers(headers)
    rows: list[tuple[int, dict[str, Any]]] = []
    for row_number, values in enumerate(reader, start=2):
        if len(values) > MAX_COLUMNS:
            raise AppFolioFileIngestionError(
                f"CSV row {row_number} exceeds the {MAX_COLUMNS}-column limit."
            )
        padded = list(values) + [""] * (len(headers) - len(values))
        if len(padded) > len(headers):
            raise AppFolioFileIngestionError(
                f"CSV row {row_number} has more values than the header row."
            )
        if not any(str(value).strip() for value in padded):
            continue
        rows.append(
            (
                row_number,
                {
                    headers[index]: _clean_cell(value)
                    for index, value in enumerate(padded)
                },
            )
        )
        if len(rows) > MAX_ROWS:
            raise AppFolioFileIngestionError(
                f"Source file exceeds the {MAX_ROWS}-row staging limit."
            )
    return ParsedTable(file_format="CSV", sheet_name="CSV", headers=headers, rows=rows)


def _xlsx_sheet_headers(ws) -> list[str]:
    first = next(ws.iter_rows(min_row=1, max_row=1), ())
    if any(getattr(cell, "data_type", None) == "f" for cell in first):
        raise AppFolioFileIngestionError("Spreadsheet formula cells are not accepted.")
    return [str(cell.value or "").strip() for cell in first]


def _looks_like_properties(headers: list[str]) -> bool:
    normalized = {_normalize_header(header) for header in headers}
    matched = 0
    for field in PROPERTY_REQUIRED:
        aliases = {_normalize_header(alias) for alias in PROPERTY_ALIASES[field]}
        if normalized & aliases:
            matched += 1
    return matched == len(PROPERTY_REQUIRED)


def _looks_like_units(headers: list[str]) -> bool:
    normalized = {_normalize_header(header) for header in headers}
    unit_name = {
        _normalize_header(alias) for alias in UNIT_ALIASES["unit_name"]
    }
    property_ref = {
        _normalize_header(alias)
        for field in ("source_property_id", "property_name")
        for alias in UNIT_ALIASES[field]
    }
    address_ref = {
        _normalize_header(alias)
        for field in ("unit_address", "address_line1")
        for alias in UNIT_ALIASES[field]
    }
    return bool(normalized & unit_name) and bool(normalized & property_ref) and bool(
        normalized & address_ref
    )


def _parse_xlsx(content: bytes, requested_sheet: str | None) -> ParsedTable:
    stream = io.BytesIO(content)
    if not zipfile.is_zipfile(stream):
        raise AppFolioFileIngestionError("XLSX source is not a valid workbook archive.")
    stream.seek(0)
    with zipfile.ZipFile(stream) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_XLSX_ENTRIES:
            raise AppFolioFileIngestionError("XLSX archive contains too many entries.")
        if sum(info.file_size for info in infos) > MAX_XLSX_UNCOMPRESSED_BYTES:
            raise AppFolioFileIngestionError("XLSX expanded content exceeds the safety limit.")
        lowered = {info.filename.lower() for info in infos}
        if any(name.endswith("vbaproject.bin") for name in lowered):
            raise AppFolioFileIngestionError("Macro-enabled spreadsheet content is not accepted.")
        try:
            content_types = archive.read("[Content_Types].xml").lower()
        except KeyError:
            content_types = b""
        if b"macroenabled" in content_types:
            raise AppFolioFileIngestionError("Macro-enabled spreadsheet content is not accepted.")

    stream.seek(0)
    try:
        workbook = load_workbook(
            stream,
            read_only=True,
            data_only=False,
            keep_links=False,
        )
    except Exception as exc:
        raise AppFolioFileIngestionError("XLSX workbook could not be parsed safely.") from exc
    try:
        if len(workbook.sheetnames) > MAX_SHEETS:
            raise AppFolioFileIngestionError(
                f"Workbook exceeds the {MAX_SHEETS}-sheet limit."
            )
        if requested_sheet:
            if requested_sheet not in workbook.sheetnames:
                raise AppFolioFileIngestionError("Requested workbook sheet was not found.")
            selected = requested_sheet
        elif len(workbook.sheetnames) == 1:
            selected = workbook.sheetnames[0]
        else:
            candidates = []
            for name in workbook.sheetnames:
                headers = _xlsx_sheet_headers(workbook[name])
                if headers and (
                    _looks_like_properties(headers) or _looks_like_units(headers)
                ):
                    candidates.append(name)
            if len(candidates) != 1:
                raise AppFolioFileIngestionError(
                    "Workbook contains multiple sheets; specify sheet_name unless exactly one supported report can be detected."
                )
            selected = candidates[0]

        ws = workbook[selected]
        headers = _xlsx_sheet_headers(ws)
        _validate_headers(headers)
        rows: list[tuple[int, dict[str, Any]]] = []
        for row_number, cells in enumerate(ws.iter_rows(min_row=2), start=2):
            if len(cells) > MAX_COLUMNS:
                raise AppFolioFileIngestionError(
                    f"Workbook row {row_number} exceeds the {MAX_COLUMNS}-column limit."
                )
            if any(getattr(cell, "data_type", None) == "f" for cell in cells):
                raise AppFolioFileIngestionError(
                    f"Spreadsheet formula cell found on row {row_number}; formulas are never evaluated."
                )
            values = [_clean_cell(cell.value) for cell in cells[: len(headers)]]
            values += [None] * (len(headers) - len(values))
            if not any(value not in (None, "") for value in values):
                continue
            rows.append(
                (
                    row_number,
                    {
                        headers[index]: values[index]
                        for index in range(len(headers))
                    },
                )
            )
            if len(rows) > MAX_ROWS:
                raise AppFolioFileIngestionError(
                    f"Source file exceeds the {MAX_ROWS}-row staging limit."
                )
        return ParsedTable(
            file_format="XLSX",
            sheet_name=selected,
            headers=headers,
            rows=rows,
        )
    finally:
        workbook.close()


def _parse_file(filename: str, content: bytes, sheet_name: str | None) -> ParsedTable:
    if len(content) > MAX_FILE_BYTES:
        raise AppFolioFileIngestionError(
            f"Source file exceeds the {MAX_FILE_BYTES // (1024 * 1024)} MB upload limit."
        )
    suffix = Path(filename).suffix.lower()
    if suffix == ".csv":
        if sheet_name:
            raise AppFolioFileIngestionError("sheet_name is only valid for XLSX uploads.")
        return _parse_csv(content)
    if suffix == ".xlsx":
        return _parse_xlsx(content, sheet_name)
    if suffix in {".xlsm", ".xls", ".xltm"}:
        raise AppFolioFileIngestionError(
            "Macro-enabled or legacy Excel formats are not accepted; export a data-only XLSX or CSV."
        )
    raise AppFolioFileIngestionError("Only CSV and XLSX source files are supported.")


def _auto_mapping(
    headers: list[str],
    aliases_by_field: dict[str, tuple[str, ...]],
) -> tuple[dict[str, str], list[str]]:
    by_normalized = {_normalize_header(header): header for header in headers}
    mapping: dict[str, str] = {}
    ambiguous: list[str] = []
    for field, aliases in aliases_by_field.items():
        matches = []
        for alias in aliases:
            header = by_normalized.get(_normalize_header(alias))
            if header is not None and header not in matches:
                matches.append(header)
        if len(matches) == 1:
            mapping[field] = matches[0]
        elif len(matches) > 1:
            ambiguous.append(field)
    return mapping, ambiguous


def _resolve_mapping(
    headers: list[str],
    *,
    resource_override: str | None,
    explicit_mapping: dict[str, str] | None,
) -> tuple[str, dict[str, str], list[str], list[str]]:
    requested = (resource_override or "").strip().upper()
    if requested not in {"", "PROPERTIES", "UNITS"}:
        raise AppFolioFileIngestionError(
            "This migration stage currently supports only verified PROPERTIES and UNITS resource mappings."
        )

    if requested == "PROPERTIES":
        resource = "PROPERTIES"
    elif requested == "UNITS":
        resource = "UNITS"
    elif _looks_like_properties(headers):
        resource = "PROPERTIES"
    elif _looks_like_units(headers):
        resource = "UNITS"
    else:
        resource = "UNKNOWN"

    aliases = (
        PROPERTY_ALIASES
        if resource == "PROPERTIES"
        else UNIT_ALIASES
        if resource == "UNITS"
        else {}
    )
    required = (
        PROPERTY_REQUIRED
        if resource == "PROPERTIES"
        else UNIT_REQUIRED
        if resource == "UNITS"
        else ()
    )
    auto_mapping, ambiguous = _auto_mapping(headers, aliases) if aliases else ({}, [])
    mapping = dict(auto_mapping)

    if explicit_mapping:
        allowed_fields = set(aliases)
        if not allowed_fields:
            # A caller must choose a supported resource before using explicit
            # mapping when automatic report detection cannot determine one.
            raise AppFolioFileIngestionError(
                "Choose resource PROPERTIES or UNITS before supplying explicit column mapping."
            )
        unknown_fields = sorted(set(explicit_mapping) - allowed_fields)
        if unknown_fields:
            raise AppFolioFileIngestionError(
                "Unknown explicit mapping fields: " + ", ".join(unknown_fields)
            )
        header_set = set(headers)
        missing_headers = sorted(
            {header for header in explicit_mapping.values() if header not in header_set}
        )
        if missing_headers:
            raise AppFolioFileIngestionError(
                "Explicit mapping references unknown source headers: "
                + ", ".join(missing_headers)
            )
        if len(set(explicit_mapping.values())) != len(explicit_mapping.values()):
            raise AppFolioFileIngestionError(
                "A source column cannot be explicitly mapped to multiple target fields."
            )
        mapping.update(explicit_mapping)
        ambiguous = [field for field in ambiguous if field not in explicit_mapping]

    missing_required = [field for field in required if field not in mapping]
    return resource, mapping, ambiguous, missing_required


def _normalized_source_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        _normalize_header(key): _clean_cell(value)
        for key, value in row.items()
    }


def _fingerprint(
    *,
    run: PlatformMigrationRun,
    parsed: ParsedTable,
    resource: str,
    mapping: dict[str, str],
) -> str:
    canonical = {
        "provider": "APPFOLIO",
        "organization_id": run.organization_id,
        "source_account_ref": run.source_account_ref,
        "resource": resource,
        "sheet_name": parsed.sheet_name,
        "mapping": {
            key: _normalize_header(value)
            for key, value in sorted(mapping.items())
        },
        "rows": [
            {
                "row_number": row_number,
                "data": _normalized_source_row(row),
            }
            for row_number, row in parsed.rows
        ],
    }
    return hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _row_fingerprint(row: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            _normalized_source_row(row),
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def _mapped_value(row: dict[str, Any], mapping: dict[str, str], field: str) -> Any:
    source = mapping.get(field)
    return _clean_cell(row.get(source)) if source else None


def stage_appfolio_file(
    db: Session,
    *,
    run: PlatformMigrationRun,
    filename: str,
    content: bytes,
    resource_override: str | None,
    sheet_name: str | None,
    explicit_mapping: dict[str, str] | None,
    platform_user_id: int,
) -> StagedUploadResult:
    if run.provider != "APPFOLIO":
        raise AppFolioFileIngestionError("Migration run is not an AppFolio run.")
    safe_filename = _safe_filename(filename)
    parsed = _parse_file(safe_filename, content, sheet_name)
    resource, mapping, ambiguous, missing_required = _resolve_mapping(
        parsed.headers,
        resource_override=resource_override,
        explicit_mapping=explicit_mapping,
    )
    fingerprint = _fingerprint(
        run=run,
        parsed=parsed,
        resource=resource,
        mapping=mapping,
    )
    replay = (
        db.query(PlatformMigrationUpload)
        .filter(
            PlatformMigrationUpload.run_id == run.id,
            PlatformMigrationUpload.organization_id == run.organization_id,
            PlatformMigrationUpload.provider == "APPFOLIO",
            PlatformMigrationUpload.normalized_fingerprint == fingerprint,
        )
        .first()
    )
    if replay is not None:
        return StagedUploadResult(upload=replay, replayed=True)

    file_sha256 = hashlib.sha256(content).hexdigest()
    upload = PlatformMigrationUpload(
        run_id=run.id,
        organization_id=run.organization_id,
        provider="APPFOLIO",
        filename=safe_filename,
        file_format=parsed.file_format,
        file_sha256=file_sha256,
        normalized_fingerprint=fingerprint,
        detected_resource=resource,
        sheet_name=parsed.sheet_name,
        headers=parsed.headers,
        column_mapping=mapping,
        validation_summary={},
        status="STAGING",
        row_count=len(parsed.rows),
        created_by_platform_user_id=platform_user_id,
    )
    db.add(upload)
    db.flush()

    valid = 0
    warning_rows = 0
    invalid = 0
    duplicates = 0
    possible_matches = 0
    seen_source_ids: set[str] = set()

    for row_number, source_row in parsed.rows:
        errors: list[str] = []
        warnings: list[str] = []
        source_id = None
        disposition = "REVIEW"
        normalized_data: dict[str, Any]

        if resource == "PROPERTIES":
            normalized_data = {
                field: _mapped_value(source_row, mapping, field)
                for field in PROPERTY_ALIASES
                if field in mapping
            }
            if ambiguous:
                errors.append(
                    "Ambiguous automatic mapping requires explicit mapping for: "
                    + ", ".join(sorted(ambiguous))
                )
            if missing_required:
                errors.append(
                    "Missing required source columns: " + ", ".join(missing_required)
                )

            source_id_value = normalized_data.get("source_id")
            source_id = str(source_id_value).strip() if source_id_value is not None else None
            if not source_id:
                errors.append("source_id is required.")
            elif source_id in seen_source_ids:
                errors.append("Duplicate AppFolio source ID in this staged upload.")
                duplicates += 1
            else:
                seen_source_ids.add(source_id)

            for field in ("name", "address_line1", "city", "state", "zip_code"):
                value = normalized_data.get(field)
                if value is None or not str(value).strip():
                    errors.append(f"{field} is required.")

            if errors:
                disposition = "INVALID"
                invalid += 1
            else:
                valid += 1
                mapped_item = (
                    db.query(PlatformMigrationItem)
                    .filter(
                        PlatformMigrationItem.run_id == run.id,
                        PlatformMigrationItem.organization_id == run.organization_id,
                        PlatformMigrationItem.provider == "APPFOLIO",
                        PlatformMigrationItem.resource == "PROPERTIES",
                        PlatformMigrationItem.source_id == source_id,
                    )
                    .first()
                )
                if mapped_item is not None:
                    disposition = "ALREADY_MAPPED"
                    warnings.append(
                        f"Source ID is already mapped to {mapped_item.target_entity} #{mapped_item.target_id}."
                    )
                else:
                    existing = (
                        db.query(Property)
                        .filter(
                            Property.organization_id == run.organization_id,
                            Property.name == normalized_data.get("name"),
                            Property.address_line1 == normalized_data.get("address_line1"),
                            Property.city == normalized_data.get("city"),
                            Property.state == normalized_data.get("state"),
                            Property.zip_code == normalized_data.get("zip_code"),
                        )
                        .first()
                    )
                    if existing is not None:
                        disposition = "POSSIBLE_MATCH"
                        possible_matches += 1
                        warnings.append(
                            f"Possible existing target property match: local property #{existing.id}."
                        )
                    elif normalized_data.get("hidden_at") not in (None, "", False, 0):
                        disposition = "REVIEW"
                        warnings.append(
                            "Source property is marked hidden; review inclusion before dry run."
                        )
                    else:
                        disposition = "NEW"
        elif resource == "UNITS":
            normalized_data = {
                field: _mapped_value(source_row, mapping, field)
                for field in UNIT_ALIASES
                if field in mapping
            }
            if ambiguous:
                errors.append(
                    "Ambiguous automatic mapping requires explicit mapping for: "
                    + ", ".join(sorted(ambiguous))
                )
            if missing_required:
                errors.append(
                    "Missing required source columns: " + ", ".join(missing_required)
                )

            unit_name = normalized_data.get("unit_name")
            if unit_name is None or not str(unit_name).strip():
                errors.append("unit_name is required.")

            source_id_value = normalized_data.get("source_id")
            source_id = str(source_id_value).strip() if source_id_value is not None else None
            if source_id:
                if source_id in seen_source_ids:
                    errors.append("Duplicate AppFolio Unit ID in this staged upload.")
                    duplicates += 1
                else:
                    seen_source_ids.add(source_id)

            source_property_value = normalized_data.get("source_property_id")
            source_property_id = (
                str(source_property_value).strip()
                if source_property_value is not None
                else None
            )

            mapped_property = None
            if source_property_id:
                mapped_property = (
                    db.query(PlatformMigrationItem)
                    .filter(
                        PlatformMigrationItem.run_id == run.id,
                        PlatformMigrationItem.organization_id == run.organization_id,
                        PlatformMigrationItem.provider == "APPFOLIO",
                        PlatformMigrationItem.resource == "PROPERTIES",
                        PlatformMigrationItem.source_id == source_property_id,
                    )
                    .first()
                )
                if mapped_property is not None:
                    target_property = (
                        db.query(Property)
                        .filter(
                            Property.id == mapped_property.target_id,
                            Property.organization_id == run.organization_id,
                            Property.is_active.is_(True),
                            Property.deleted_at.is_(None),
                        )
                        .first()
                    )
                    if (
                        mapped_property.target_entity != "PROPERTY"
                        or target_property is None
                    ):
                        errors.append(
                            "Mapped source Property ID does not resolve to an active same-organization Property."
                        )

            if errors:
                disposition = "INVALID"
                invalid += 1
            else:
                valid += 1
                mapped_unit = None
                if source_id:
                    mapped_unit = (
                        db.query(PlatformMigrationItem)
                        .filter(
                            PlatformMigrationItem.run_id == run.id,
                            PlatformMigrationItem.organization_id == run.organization_id,
                            PlatformMigrationItem.provider == "APPFOLIO",
                            PlatformMigrationItem.resource == "UNITS",
                            PlatformMigrationItem.source_id == source_id,
                        )
                        .first()
                    )
                if mapped_unit is not None:
                    disposition = "ALREADY_MAPPED"
                    warnings.append(
                        f"Source Unit ID is already mapped to {mapped_unit.target_entity} #{mapped_unit.target_id}."
                    )
                elif not source_property_id:
                    disposition = "REVIEW"
                    warnings.append(
                        "Property ID was not supplied; Unit-to-Property linkage must be resolved before dry run or commit."
                    )
                elif mapped_property is None:
                    disposition = "REVIEW"
                    warnings.append(
                        f"Source Property ID {source_property_id} has no durable Property mapping in this migration run."
                    )
                elif not source_id:
                    disposition = "REVIEW"
                    warnings.append(
                        "Unit ID was not supplied; durable Unit source identity must be resolved before dry run or commit."
                    )
                else:
                    exact = (
                        db.query(Unit)
                        .filter(
                            Unit.property_id == target_property.id,
                            Unit.unit_number == str(unit_name).strip(),
                            Unit.is_active.is_(True),
                            Unit.deleted_at.is_(None),
                        )
                        .first()
                    )
                    candidate = exact
                    if candidate is None:
                        candidate = (
                            db.query(Unit)
                            .filter(
                                Unit.property_id == target_property.id,
                                func.lower(Unit.unit_number)
                                == str(unit_name).strip().lower(),
                                Unit.is_active.is_(True),
                                Unit.deleted_at.is_(None),
                            )
                            .first()
                        )
                    if candidate is not None:
                        disposition = "POSSIBLE_MATCH"
                        possible_matches += 1
                        match_kind = (
                            "exact unit-number"
                            if candidate.unit_number == str(unit_name).strip()
                            else "case-insensitive unit-number"
                        )
                        warnings.append(
                            f"Possible existing target unit match: local unit #{candidate.id} ({match_kind})."
                        )
                    else:
                        disposition = "NEW"
        else:
            normalized_data = _normalized_source_row(source_row)
            errors.append(
                "Report type could not be detected safely; choose PROPERTIES or UNITS and supply explicit column mapping."
            )
            disposition = "INVALID"
            invalid += 1

        if warnings:
            warning_rows += 1

        db.add(
            PlatformMigrationStagedRow(
                upload_id=upload.id,
                run_id=run.id,
                organization_id=run.organization_id,
                provider="APPFOLIO",
                resource=resource,
                row_number=row_number,
                source_id=source_id,
                disposition=disposition,
                row_fingerprint=_row_fingerprint(source_row),
                normalized_data=normalized_data,
                warnings=warnings,
                errors=errors,
            )
        )

    summary = {
        "total": len(parsed.rows),
        "valid": valid,
        "warnings": warning_rows,
        "invalid": invalid,
        "duplicates": duplicates,
        "possible_existing_matches": possible_matches,
        "missing_required_columns": missing_required,
        "ambiguous_mapping_fields": sorted(ambiguous),
    }
    if resource == "UNITS":
        unit_rows = (
            db.query(PlatformMigrationStagedRow)
            .filter(
                PlatformMigrationStagedRow.upload_id == upload.id,
                PlatformMigrationStagedRow.resource == "UNITS",
            )
            .all()
        )
        summary["unresolved_property_links"] = sum(
            1
            for row in unit_rows
            if any("Property" in warning for warning in (row.warnings or []))
        )
        summary["missing_unit_source_ids"] = sum(
            1
            for row in unit_rows
            if any("Unit ID was not supplied" in warning for warning in (row.warnings or []))
        )
    if resource == "UNKNOWN" or missing_required or ambiguous:
        upload.status = "MAPPING_REQUIRED"
    elif invalid:
        upload.status = "STAGED_WITH_ERRORS"
    elif warning_rows:
        upload.status = "REVIEW_REQUIRED"
    else:
        upload.status = "STAGED"
    upload.validation_summary = summary

    # Any new staging/mapping state makes an earlier dry run stale.
    run.last_dry_run_fingerprint = None
    run.last_dry_run_summary = None
    run.status = "STAGED"
    db.flush()
    return StagedUploadResult(upload=upload, replayed=False)
