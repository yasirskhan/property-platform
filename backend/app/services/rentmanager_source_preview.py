"""Read-only quality assessment for a staff-proposed RentManager export mapping.

No source rows, PII, provider credentials or customer mutations are persisted or returned.
The proposed mapping has no authority to enable staging, matching or commit.
"""
from typing import Any


def assess_source_rows(rows: list[tuple[int, dict[str, Any]]], mapping: dict[str, str],
                       identity_field: str | None = None) -> dict:
    total = len(rows)
    missing = {field: 0 for field in mapping}
    duplicates = 0
    seen: set[str] = set()
    for _, source in rows:
        for field, header in mapping.items():
            value = source.get(header)
            if value is None or not str(value).strip():
                missing[field] += 1
        if identity_field and identity_field in mapping:
            value = source.get(mapping[identity_field])
            stable_id = str(value).strip() if value is not None else ""
            if stable_id:
                if stable_id in seen:
                    duplicates += 1
                else:
                    seen.add(stable_id)
    return {
        "total_rows": total,
        "missing_values_by_proposed_field": missing,
        "duplicate_nonempty_identity_rows": duplicates,
        "identity_field_evaluated": identity_field if identity_field in mapping else None,
        "rows_returned": False,
        "source_contract_verified": False,
        "mapping_authorized": False,
        "staging_mutation": False,
        "customer_business_mutation": False,
        "can_stage_import": False,
        "can_commit_import": False,
    }
