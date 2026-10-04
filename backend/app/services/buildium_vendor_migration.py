"""Buildium Vendor identity mapping for Phase 4.14.

This bounded adapter accepts documented Buildium Vendor identity fields and
maps them only to an existing same-organization target Vendor. It does not
create a Vendor, infer trade/preferred-property assignments, or store raw
provider payloads/credentials.
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
from app.models.vendor import Vendor


class BuildiumVendorMigrationError(ValueError):
    pass


@dataclass(frozen=True)
class VendorDryRunResult:
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
class VendorCommitResult:
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


def _source_id(value: Any) -> str | None:
    if isinstance(value,bool):
        return None
    try:
        n=int(value)
    except (TypeError,ValueError):
        return None
    return str(n) if n>0 else None


def _email(value: Any) -> tuple[str | None,str | None]:
    text=_clean(value)
    if text is None:
        return None,None
    if len(text)>255 or not re.fullmatch(r"[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+",text):
        return None,"PrimaryEmail must be one valid email when supplied."
    return text.lower(),None


def _vendor_name(record: dict[str,Any]) -> tuple[str | None,str | None,list[str]]:
    is_company=record.get("IsCompany")
    if not isinstance(is_company,bool):
        return None,"IsCompany must be a boolean from Buildium.",[]
    warnings:list[str]=[]
    if is_company:
        name=_clean(record.get("CompanyName"))
        if not name:
            return None,"CompanyName is required when IsCompany is true.",[]
        if len(name)>255:
            return None,"CompanyName exceeds 255 characters.",[]
        return name,None,warnings
    first=_clean(record.get("FirstName"))
    last=_clean(record.get("LastName"))
    if not first or not last:
        return None,"FirstName and LastName are required when IsCompany is false.",[]
    name=f"{first} {last}"
    if len(name)>255:
        return None,"Individual vendor display name exceeds 255 characters.",[]
    warnings.append(
        "Buildium marks this Vendor as an individual; the target Vendor uses one company_name/display field. "
        "The source full name is used only for reviewed identity matching and is never treated as a legal company name."
    )
    return name,None,warnings


def _normalize_resolutions(items:list[dict[str,Any]]|None)->dict[str,dict[str,Any]]:
    out={}
    for item in items or []:
        sid=_source_id(item.get("source_id"))
        if sid is None:
            raise BuildiumVendorMigrationError("Vendor review source_id must be a positive integer.")
        if sid in out:
            raise BuildiumVendorMigrationError(f"Duplicate Vendor review decision for source ID {sid}.")
        action=_clean(item.get("action"))
        if action not in {"MATCH_EXISTING","SKIP"}:
            raise BuildiumVendorMigrationError("Vendor review supports only MATCH_EXISTING or SKIP.")
        target=item.get("target_vendor_id")
        if action=="MATCH_EXISTING":
            if isinstance(target,bool):
                raise BuildiumVendorMigrationError("MATCH_EXISTING requires a positive target Vendor ID.")
            try: target=int(target)
            except (TypeError,ValueError):
                raise BuildiumVendorMigrationError("MATCH_EXISTING requires a positive target Vendor ID.")
            if target<1:
                raise BuildiumVendorMigrationError("MATCH_EXISTING requires a positive target Vendor ID.")
        elif target is not None:
            raise BuildiumVendorMigrationError("target_vendor_id is only valid for MATCH_EXISTING.")
        out[sid]={"source_id":int(sid),"action":action,"target_vendor_id":target}
    return out


def _fingerprint(*,run:PlatformMigrationRun,records:list[dict[str,Any]],resolutions:list[dict[str,Any]]|None)->str:
    rs=_normalize_resolutions(resolutions)
    canonical=json.dumps({
        "provider":"BUILDIUM",
        "resource":"VENDORS",
        "organization_id":run.organization_id,
        "source_account_ref":run.source_account_ref,
        "records":records,
        "resolutions":[rs[k] for k in sorted(rs,key=int)],
    },sort_keys=True,separators=(",",":"),default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def dry_run_vendors(db:Session,*,run:PlatformMigrationRun,records:list[dict[str,Any]],resolutions:list[dict[str,Any]]|None=None)->VendorDryRunResult:
    if run.provider!="BUILDIUM":
        raise BuildiumVendorMigrationError("Migration run is not a Buildium run.")
    if not records:
        raise BuildiumVendorMigrationError("At least one Buildium Vendor record is required.")
    fp=_fingerprint(run=run,records=records,resolutions=resolutions)
    replayed=run.last_dry_run_fingerprint==fp
    rs=_normalize_resolutions(resolutions)
    rows=[]; seen=set(); reviewable_ids=set()
    reviewable=skipped=invalid=warnings_count=0
    for record in records:
        sid=_source_id(record.get("Id"))
        if sid is None:
            rows.append({"source_id":None,"reviewable":False,"reason":"Buildium Vendor Id must be a positive integer.","mapped":None,"warnings":[]}); invalid+=1; continue
        if sid in seen:
            rows.append({"source_id":sid,"reviewable":False,"reason":"Duplicate Buildium Vendor Id in this dry run.","mapped":None,"warnings":[]}); invalid+=1; continue
        seen.add(sid)
        name,error,row_warnings=_vendor_name(record)
        email,email_error=_email(record.get("PrimaryEmail"))
        if error or email_error:
            rows.append({"source_id":sid,"reviewable":False,"reason":" ".join(x for x in (error,email_error) if x),"mapped":None,"warnings":[]}); invalid+=1; continue
        reviewable_ids.add(sid)
        candidate=None
        if email:
            candidate=(db.query(Vendor).filter(Vendor.organization_id==run.organization_id,Vendor.is_active.is_(True),Vendor.deleted_at.is_(None),func.lower(Vendor.business_email)==email).first())
        if candidate is None:
            candidate=(db.query(Vendor).filter(Vendor.organization_id==run.organization_id,Vendor.is_active.is_(True),Vendor.deleted_at.is_(None),func.lower(Vendor.company_name)==name.lower()).first())
        if candidate:
            row_warnings.append(f"Possible existing target Vendor match: local Vendor #{candidate.id}; explicit MATCH_EXISTING review is required.")
        else:
            row_warnings.append("No active same-organization target Vendor candidate was found; this bounded batch does not auto-create one.")
        durable=(db.query(PlatformMigrationItem).filter(PlatformMigrationItem.run_id==run.id,PlatformMigrationItem.organization_id==run.organization_id,PlatformMigrationItem.provider=="BUILDIUM",PlatformMigrationItem.resource=="VENDORS",PlatformMigrationItem.source_id==sid).first())
        resolution=rs.get(sid); action=resolution["action"] if resolution else None; target_id=resolution["target_vendor_id"] if resolution else None
        if durable:
            if durable.target_entity!="VENDOR":
                raise BuildiumVendorMigrationError("Buildium Vendor mapping is inconsistent and requires manual review.")
            if resolution is not None and (action!="MATCH_EXISTING" or target_id!=durable.target_id):
                raise BuildiumVendorMigrationError(f"Buildium source Vendor ID {sid} already has a durable mapping and cannot be re-resolved.")
            row_warnings.append(f"Buildium source Vendor ID {sid} is already durably mapped to local Vendor #{durable.target_id}; commit will replay.")
        if action=="MATCH_EXISTING":
            target=(db.query(Vendor).filter(Vendor.id==target_id,Vendor.organization_id==run.organization_id,Vendor.is_active.is_(True),Vendor.deleted_at.is_(None)).first())
            if target is None:
                raise BuildiumVendorMigrationError(f"Reviewed target Vendor #{target_id} is not active in the target organization.")
            email_matches=not email or (target.business_email and target.business_email.lower()==email)
            name_matches=target.company_name.strip().casefold()==name.casefold()
            if not (email_matches or name_matches):
                raise BuildiumVendorMigrationError("Reviewed Vendor no longer matches the Buildium source name/email identity.")
            row_warnings.append(f"Reviewed MATCH_EXISTING target: local Vendor #{target.id}; commit creates mapping metadata only.")
        elif action=="SKIP":
            rows.append({"source_id":sid,"reviewable":False,"reason":"Explicitly skipped after Buildium Vendor review.","mapped":None,"warnings":row_warnings,"resolution_action":"SKIP","resolution_target_vendor_id":None}); skipped+=1; warnings_count+=len(row_warnings); continue
        rows.append({"source_id":sid,"reviewable":True,"reason":None,"mapped":{"display_name":name,"primary_email":email,"target_vendor_id":target_id},"warnings":row_warnings,"resolution_action":action,"resolution_target_vendor_id":target_id})
        reviewable+=1; warnings_count+=len(row_warnings)
    unknown=sorted(set(rs)-reviewable_ids,key=int)
    if unknown:
        raise BuildiumVendorMigrationError("Vendor review decisions may reference only otherwise-valid source rows: "+", ".join(unknown))
    summary={"resource":"VENDORS","transport":"BUILDIUM_API_V1_RECORDS","total":len(records),"reviewable":reviewable,"skipped_review":skipped,"invalid":invalid,"warning_count":warnings_count,"vendors_created":False,"preferred_vendor_links_created":False,"trade_inferred":False,"raw_payload_stored":False,"provider_credentials_stored":False}
    if not replayed:
        run.last_dry_run_fingerprint=fp; run.last_dry_run_summary=summary; run.status="DRY_RUN_READY"
    return VendorDryRunResult(fp,replayed,len(records),reviewable,skipped,invalid,warnings_count,rows,summary)


def commit_vendors(db:Session,*,run:PlatformMigrationRun,records:list[dict[str,Any]],expected_fingerprint:str,platform_user_id:int,resolutions:list[dict[str,Any]]|None=None)->VendorCommitResult:
    fp=_fingerprint(run=run,records=records,resolutions=resolutions)
    if expected_fingerprint!=fp:
        raise BuildiumVendorMigrationError("Commit payload or Vendor review state does not match the supplied dry-run fingerprint.")
    if run.last_dry_run_fingerprint!=fp:
        raise BuildiumVendorMigrationError("Commit requires the exact latest successful Buildium Vendor dry run.")
    preview=dry_run_vendors(db,run=run,records=records,resolutions=resolutions)
    if preview.invalid:
        raise BuildiumVendorMigrationError("Vendor commit is blocked while the dry run contains invalid records.")
    rs=_normalize_resolutions(resolutions)
    valid=[row for row in preview.rows if row["reviewable"]]
    missing=[]
    for row in valid:
        sid=str(row["source_id"])
        prior=(db.query(PlatformMigrationItem).filter(PlatformMigrationItem.run_id==run.id,PlatformMigrationItem.organization_id==run.organization_id,PlatformMigrationItem.provider=="BUILDIUM",PlatformMigrationItem.resource=="VENDORS",PlatformMigrationItem.source_id==sid).first())
        if not prior and row["resolution_action"]!="MATCH_EXISTING": missing.append(sid)
    if missing:
        raise BuildiumVendorMigrationError("Vendor controlled mapping requires explicit MATCH_EXISTING or SKIP review for every valid source row: "+", ".join(missing))
    rows=[]; matched=0; changed=False
    for row in valid:
        sid=str(row["source_id"])
        prior=(db.query(PlatformMigrationItem).filter(PlatformMigrationItem.run_id==run.id,PlatformMigrationItem.organization_id==run.organization_id,PlatformMigrationItem.provider=="BUILDIUM",PlatformMigrationItem.resource=="VENDORS",PlatformMigrationItem.source_id==sid).first())
        if prior:
            if prior.target_entity!="VENDOR":
                raise BuildiumVendorMigrationError("Buildium Vendor mapping is inconsistent.")
            target=db.query(Vendor).filter(Vendor.id==prior.target_id,Vendor.organization_id==run.organization_id).first()
            if target is None: raise BuildiumVendorMigrationError("Previously mapped target Vendor is missing.")
            rows.append({"source_id":sid,"target_vendor_id":target.id,"replayed":True}); continue
        target_id=rs[sid]["target_vendor_id"]
        target=(db.query(Vendor).filter(Vendor.id==target_id,Vendor.organization_id==run.organization_id,Vendor.is_active.is_(True),Vendor.deleted_at.is_(None)).first())
        if target is None: raise BuildiumVendorMigrationError(f"Reviewed target Vendor #{target_id} is no longer active.")
        source_name=row["mapped"]["display_name"]; source_email=row["mapped"]["primary_email"]
        email_matches=not source_email or (target.business_email and target.business_email.lower()==source_email)
        name_matches=target.company_name.strip().casefold()==source_name.casefold()
        if not (email_matches or name_matches): raise BuildiumVendorMigrationError("Reviewed Vendor identity changed after dry run.")
        db.add(PlatformMigrationItem(run_id=run.id,organization_id=run.organization_id,provider="BUILDIUM",resource="VENDORS",source_id=sid,target_entity="VENDOR",target_id=target.id,source_fingerprint=fp,created_by_platform_user_id=platform_user_id))
        rows.append({"source_id":sid,"target_vendor_id":target.id,"replayed":False}); matched+=1; changed=True
    review_recorded=False
    if changed:
        run.status="VENDORS_MAPPED"; db.flush()
    elif preview.skipped_review and not rows and run.status=="DRY_RUN_READY":
        run.status="VENDORS_REVIEWED"; db.flush(); review_recorded=True
    return VendorCommitResult(fp,not changed and not review_recorded,matched,preview.skipped_review,preview.warning_count,rows)
