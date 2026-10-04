"""Buildium Rental Tenant identity mapping for Phase 4.14.

Tenant records map only to existing same-organization TENANT users. Buildium
UserLeaseId is preserved in the reviewed fingerprint/preview as relationship
evidence for a later lease reconciliation batch. No user, lease, charge,
security-deposit, tax, or payment record is created here.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.user import User, UserRole


class BuildiumTenantMigrationError(ValueError):
    pass


@dataclass(frozen=True)
class TenantDryRunResult:
    fingerprint: str
    replayed: bool
    total: int
    reviewable: int
    skipped_review: int
    invalid: int
    warning_count: int
    rows: list[dict[str, Any]]
    summary: dict[str, Any]


@dataclass(frozen=True)
class TenantCommitResult:
    fingerprint: str
    replayed: bool
    matched_existing: int
    skipped_review: int
    warning_count: int
    rows: list[dict[str, Any]]


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text=str(value).strip()
    return text or None


def _positive_id(value: Any) -> str | None:
    if isinstance(value,bool):
        return None
    try: n=int(value)
    except (TypeError,ValueError): return None
    return str(n) if n>0 else None


def _email(value: Any) -> tuple[str | None,str | None]:
    text=_clean(value)
    if not text:
        return None,"Email is required for safe mapping to an existing TENANT user."
    if len(text)>255 or not re.fullmatch(r"[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+",text):
        return None,"Email must contain one valid source email address."
    return text.lower(),None


def _name(record:dict[str,Any])->tuple[str|None,str|None]:
    first=_clean(record.get("FirstName")); last=_clean(record.get("LastName"))
    if not first or not last: return None,"FirstName and LastName are required."
    if len(first)>100 or len(last)>100: return None,"FirstName or LastName exceeds target limits."
    return f"{first} {last}",None


def _normalize_resolutions(items:list[dict[str,Any]]|None)->dict[str,dict[str,Any]]:
    out={}
    for item in items or []:
        sid=_positive_id(item.get("source_id"))
        if sid is None: raise BuildiumTenantMigrationError("Tenant review source_id must be a positive integer.")
        if sid in out: raise BuildiumTenantMigrationError(f"Duplicate Tenant review decision for source ID {sid}.")
        action=_clean(item.get("action"))
        if action not in {"MATCH_EXISTING","SKIP"}: raise BuildiumTenantMigrationError("Tenant review supports only MATCH_EXISTING or SKIP.")
        target=item.get("target_tenant_user_id")
        if action=="MATCH_EXISTING":
            if isinstance(target,bool): raise BuildiumTenantMigrationError("MATCH_EXISTING requires a positive target TENANT user ID.")
            try: target=int(target)
            except (TypeError,ValueError): raise BuildiumTenantMigrationError("MATCH_EXISTING requires a positive target TENANT user ID.")
            if target<1: raise BuildiumTenantMigrationError("MATCH_EXISTING requires a positive target TENANT user ID.")
        elif target is not None:
            raise BuildiumTenantMigrationError("target_tenant_user_id is only valid for MATCH_EXISTING.")
        out[sid]={"source_id":int(sid),"action":action,"target_tenant_user_id":target}
    return out


def _fingerprint(*,run:PlatformMigrationRun,records:list[dict[str,Any]],resolutions:list[dict[str,Any]]|None)->str:
    rs=_normalize_resolutions(resolutions)
    payload={"provider":"BUILDIUM","resource":"TENANTS","organization_id":run.organization_id,"source_account_ref":run.source_account_ref,"records":records,"resolutions":[rs[k] for k in sorted(rs,key=int)]}
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()


def dry_run_tenants(db:Session,*,run:PlatformMigrationRun,records:list[dict[str,Any]],resolutions:list[dict[str,Any]]|None=None)->TenantDryRunResult:
    if run.provider!="BUILDIUM": raise BuildiumTenantMigrationError("Migration run is not a Buildium run.")
    if not records: raise BuildiumTenantMigrationError("At least one Buildium Rental Tenant record is required.")
    fp=_fingerprint(run=run,records=records,resolutions=resolutions); replayed=run.last_dry_run_fingerprint==fp
    rs=_normalize_resolutions(resolutions)
    rows=[]; seen=set(); valid_ids=set(); reviewable=skipped=invalid=warning_count=0
    for record in records:
        sid=_positive_id(record.get("Id"))
        if sid is None:
            rows.append({"source_id":None,"reviewable":False,"reason":"Buildium Tenant Id must be a positive integer.","mapped":None,"warnings":[]}); invalid+=1; continue
        if sid in seen:
            rows.append({"source_id":sid,"reviewable":False,"reason":"Duplicate Buildium Tenant Id in this dry run.","mapped":None,"warnings":[]}); invalid+=1; continue
        seen.add(sid)
        email,email_error=_email(record.get("Email")); display,name_error=_name(record)
        user_lease_raw=record.get("UserLeaseId")
        user_lease_id=None
        if user_lease_raw is not None:
            user_lease_id=_positive_id(user_lease_raw)
            if user_lease_id is None:
                name_error=(name_error+" " if name_error else "")+"UserLeaseId must be a positive integer when supplied."
        if email_error or name_error:
            rows.append({"source_id":sid,"reviewable":False,"reason":" ".join(x for x in (email_error,name_error) if x),"mapped":None,"warnings":[]}); invalid+=1; continue
        valid_ids.add(sid)
        warnings=[
            "Buildium UserLeaseId is preserved only as source membership evidence; this batch creates no Lease or occupancy relationship.",
            "Buildium TaxId, addresses, alternate email, emergency contact, comments, move dates and other private/source fields are not promoted into target facts by this identity-mapping batch.",
        ]
        candidate=(db.query(User).filter(User.organization_id==run.organization_id,User.role==UserRole.TENANT,User.is_active.is_(True),User.deleted_at.is_(None),func.lower(User.email)==email).first())
        if candidate: warnings.append(f"Possible existing target TENANT match by exact source email: local TENANT #{candidate.id}; explicit MATCH_EXISTING review is required.")
        else: warnings.append("No active same-organization TENANT with this exact source email was found; this batch does not create login identities.")
        durable=(db.query(PlatformMigrationItem).filter(PlatformMigrationItem.run_id==run.id,PlatformMigrationItem.organization_id==run.organization_id,PlatformMigrationItem.provider=="BUILDIUM",PlatformMigrationItem.resource=="TENANTS",PlatformMigrationItem.source_id==sid).first())
        resolution=rs.get(sid); action=resolution["action"] if resolution else None; target_id=resolution["target_tenant_user_id"] if resolution else None
        if durable:
            if durable.target_entity!="TENANT_USER": raise BuildiumTenantMigrationError("Buildium Tenant mapping is inconsistent.")
            if resolution is not None and (action!="MATCH_EXISTING" or target_id!=durable.target_id): raise BuildiumTenantMigrationError(f"Buildium source Tenant ID {sid} already has a durable mapping and cannot be re-resolved.")
            warnings.append(f"Buildium source Tenant ID {sid} is already durably mapped to local TENANT #{durable.target_id}; commit will replay.")
        if action=="MATCH_EXISTING":
            target=(db.query(User).filter(User.id==target_id,User.organization_id==run.organization_id,User.role==UserRole.TENANT,User.is_active.is_(True),User.deleted_at.is_(None)).first())
            if target is None: raise BuildiumTenantMigrationError(f"Reviewed target TENANT #{target_id} is not active in the target organization.")
            if target.email.lower()!=email: raise BuildiumTenantMigrationError("Reviewed TENANT email no longer matches the exact Buildium source email.")
            warnings.append(f"Reviewed MATCH_EXISTING target: local TENANT #{target.id}; commit creates mapping metadata only.")
        elif action=="SKIP":
            rows.append({"source_id":sid,"reviewable":False,"reason":"Explicitly skipped after Buildium Tenant review.","mapped":None,"warnings":warnings,"resolution_action":"SKIP","resolution_target_tenant_user_id":None}); skipped+=1; warning_count+=len(warnings); continue
        rows.append({"source_id":sid,"reviewable":True,"reason":None,"mapped":{"display_name":display,"email":email,"user_lease_id":user_lease_id,"target_tenant_user_id":target_id},"warnings":warnings,"resolution_action":action,"resolution_target_tenant_user_id":target_id}); reviewable+=1; warning_count+=len(warnings)
    unknown=sorted(set(rs)-valid_ids,key=int)
    if unknown: raise BuildiumTenantMigrationError("Tenant review decisions may reference only otherwise-valid source rows: "+", ".join(unknown))
    summary={"resource":"TENANTS","transport":"BUILDIUM_API_V1_RECORDS","total":len(records),"reviewable":reviewable,"skipped_review":skipped,"invalid":invalid,"warning_count":warning_count,"tenant_users_created":False,"leases_created":False,"occupancy_inferred":False,"tax_data_stored":False,"raw_payload_stored":False,"provider_credentials_stored":False}
    if not replayed:
        run.last_dry_run_fingerprint=fp; run.last_dry_run_summary=summary; run.status="DRY_RUN_READY"
    return TenantDryRunResult(fp,replayed,len(records),reviewable,skipped,invalid,warning_count,rows,summary)


def commit_tenants(db:Session,*,run:PlatformMigrationRun,records:list[dict[str,Any]],expected_fingerprint:str,platform_user_id:int,resolutions:list[dict[str,Any]]|None=None)->TenantCommitResult:
    fp=_fingerprint(run=run,records=records,resolutions=resolutions)
    if expected_fingerprint!=fp: raise BuildiumTenantMigrationError("Commit payload or Tenant review state does not match the supplied dry-run fingerprint.")
    if run.last_dry_run_fingerprint!=fp: raise BuildiumTenantMigrationError("Commit requires the exact latest successful Buildium Tenant dry run.")
    preview=dry_run_tenants(db,run=run,records=records,resolutions=resolutions)
    if preview.invalid: raise BuildiumTenantMigrationError("Tenant commit is blocked while the dry run contains invalid records.")
    rs=_normalize_resolutions(resolutions); valid=[x for x in preview.rows if x["reviewable"]]
    missing=[]
    for row in valid:
        sid=str(row["source_id"])
        prior=(db.query(PlatformMigrationItem).filter(PlatformMigrationItem.run_id==run.id,PlatformMigrationItem.organization_id==run.organization_id,PlatformMigrationItem.provider=="BUILDIUM",PlatformMigrationItem.resource=="TENANTS",PlatformMigrationItem.source_id==sid).first())
        if not prior and row["resolution_action"]!="MATCH_EXISTING": missing.append(sid)
    if missing: raise BuildiumTenantMigrationError("Tenant controlled mapping requires explicit MATCH_EXISTING or SKIP review for every valid source row: "+", ".join(missing))
    rows=[]; matched=0; changed=False
    for row in valid:
        sid=str(row["source_id"])
        prior=(db.query(PlatformMigrationItem).filter(PlatformMigrationItem.run_id==run.id,PlatformMigrationItem.organization_id==run.organization_id,PlatformMigrationItem.provider=="BUILDIUM",PlatformMigrationItem.resource=="TENANTS",PlatformMigrationItem.source_id==sid).first())
        if prior:
            if prior.target_entity!="TENANT_USER": raise BuildiumTenantMigrationError("Buildium Tenant mapping is inconsistent.")
            target=db.query(User).filter(User.id==prior.target_id,User.organization_id==run.organization_id,User.role==UserRole.TENANT).first()
            if target is None: raise BuildiumTenantMigrationError("Previously mapped target TENANT is missing.")
            rows.append({"source_id":sid,"target_tenant_user_id":target.id,"replayed":True}); continue
        target_id=rs[sid]["target_tenant_user_id"]
        target=(db.query(User).filter(User.id==target_id,User.organization_id==run.organization_id,User.role==UserRole.TENANT,User.is_active.is_(True),User.deleted_at.is_(None)).first())
        if target is None: raise BuildiumTenantMigrationError(f"Reviewed target TENANT #{target_id} is no longer active.")
        if target.email.lower()!=row["mapped"]["email"]: raise BuildiumTenantMigrationError("Reviewed target TENANT email changed after dry run.")
        db.add(PlatformMigrationItem(run_id=run.id,organization_id=run.organization_id,provider="BUILDIUM",resource="TENANTS",source_id=sid,target_entity="TENANT_USER",target_id=target.id,source_fingerprint=fp,created_by_platform_user_id=platform_user_id))
        rows.append({"source_id":sid,"target_tenant_user_id":target.id,"replayed":False}); matched+=1; changed=True
    review_recorded=False
    if changed: run.status="TENANTS_MAPPED"; db.flush()
    elif preview.skipped_review and not rows and run.status=="DRY_RUN_READY": run.status="TENANTS_REVIEWED"; db.flush(); review_recorded=True
    return TenantCommitResult(fp,not changed and not review_recorded,matched,preview.skipped_review,preview.warning_count,rows)
