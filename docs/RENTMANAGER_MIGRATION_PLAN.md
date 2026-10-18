# PHASE 4.16 — RENTMANAGER MIGRATION FOUNDATION

Status: **SOURCE-INDEPENDENT FOUNDATION VERIFIED; FULL MIGRATION SOURCE-CONTRACT BLOCKED** (October 18, 2026)

## Decision and release boundary

Phase 4.15 Yardi export/ETL support must close as a **bounded, source-supported migration foundation**, not as a claim that every Yardi business entity imports. The verified Yardi path supports provider-labelled runs, explicit CSV/XLSX field mapping, staging, duplicate and missing-field diagnostics, read-only reconciliation, exact review fingerprints and explicit existing-target metadata bindings. Unverified Yardi lease/occupancy creation, owner-property allocations, accounting/AR/AP/checks/GL/budgets and private API interfaces remain separately blocked pending authoritative source contracts. Do not silently introduce customer mutation.

Phase 4.16 next covers **RentManager**. Its goal is the same safe provider-labelled staged import, reusing the common PlatformMigrationRun/Upload/StagedRow/Item models, with explicit source contract approval before any direct API access or customer writes. Do not assume RentManager's API route or authentication model from vendor marketing material.

## First implementation milestone

1. Confirm backend provider normalization and any database constraints accept `RENTMANAGER` without impacting existing Yardi, AppFolio or Buildium runs.
2. Add staff-authenticated create/list/get RentManager migration-run endpoints, server-enforced provider name, bounded nonsecret source account reference, organization existence checks, role gating, no-store responses and append-only redacted create audit.
3. Add tests that reject unrelated provider runs, inactive organizations, unauthorized sales/billing users and secrets in the source account reference. No new customer business rows.
4. Add read-only resource readiness reporting; unsupported source contracts must clearly say blocked and never imply controlled commit is enabled.
5. Only then add explicitly mapped CSV/XLSX staging where authoritative export column contracts are available, using common bounded parsers and fingerprint/replay controls. Avoid copying provider-specific assumptions.
6. Obtain exact-SHA six-job CI success, update `AI_HANDOFF.md`, and continue in bounded batches.

## Definition of done and remaining dependencies

Foundation completion: verified staff run UX, safe backend scope and upload contract boundaries, provider isolation, auditable explicit review, no customer mutations, and source blockers documented. Full migration completion requires separately documented authorized fields, record grain, identity relationships, financial signs and periods for each resource. No unsupported accounting posts or invented transport.

Sole publication branch: `chatgpt/checkpoint-005-safety`. Never modify `main`, create another branch, force-push, or touch `Zargul-Silver-Marquee`.

## Foundation closeout: implementation and product limitations (2026-10-17)

The repository now implements the source-independent Phase 4.16 foundation: platform-role-scoped provider-labelled RentManager runs; active-org and provider isolation; safe nonsecret references and creation audit; list/get/run-specific and global readiness; explicit disabled ingestion/API/controlled-commit capabilities; and a bounded CSV/XLSX, data-only file inspector returning headers, indexed unmapped columns, row counts, file format/sheet, and a SHA-256 file identity. The inspector never persists raw file bytes, staged rows, or customer business records. It does not invent a RentManager target schema. Unsupported and macro-enabled formats are rejected. The endpoint is no-store.

**This closes the source-independent foundation ONLY after exact-SHA six-job CI passes.** Provider-specific mapped source staging, identity reconciliation and any actual customer-data migration are **BLOCKED BY VERIFIED SOURCE CONTRACT** until an authorized RentManager export documents fields, per-row record grain, stable identifiers, relationship semantics and for finance the periods, signs and settlement state. The real vendor API requires an official customer/partner contract and verified authentication, endpoints and pagination. Never treat inspected headers as that contract.

**Follow-up phase work:** source-contract intake, field-by-field review/authorization, controlled metadata staging with exact fingerprints, and separately proven customer mutation gates. The full Phase 4.16 migration integration remains PARTIAL and must not be described as complete until that evidence exists.

## Official API documentation located (2026-10-17)

Rent Manager (London Computer Systems) publicly describes a read/write Rent Manager Online Web API and a separate read-only Open Access database capability: https://www.rentmanager.com/software-customization/ . Rent Manager 12's published Web API technical reference is available at https://info.rentmanager.com/hubfs/PDFs/Technical%20Documentation.pdf . This supersedes any blanket statement that *no official Rent Manager API documentation exists*.

**Contract gate retained:** Public documentation is not authorization to call a customer's account, and by itself does not prove the actual customer's enabled API edition, tenant hostname, authentication setup, resource fields, permissions or financial sign conventions. A separate vetted customer-specific binding and read-only resource adapter must be proven before enabling migration. The application intentionally has no credentials stored in migration run source_account_ref, and API transport remains disabled. Never confuse **Rent Manager property management** with **Rentman event equipment software**, whose unrelated API uses api.rentman.net.

## Verified operational checkpoint — October 18, 2026

At exact SHA `204135957b0debc518e8a52beea6dda940de40b2`, GitHub Actions run `39133733722` finished SUCCESS. Source-independent implementation now includes safe organization/provider-scoped runs, read-only CSV/XLSX inspection and raw-byte SHA-256 identity, staff-proposed field mapping validation, nonpersistent aggregate source-quality preview (missing mapped values and duplicate provided identity), and optional exact inspected-export SHA-256 match for that preview. Staff roles are enforced, source rows are not returned/stored, and no staging, accounting or customer-business mutation is authorized.

**Release gate for full integration:** Obtain customer-authorized Rent Manager export(s) and a documented source contract identifying provider product/edition, resource and row grain, stable record IDs, parent/child relationship keys, null/duplicate behavior, effective dates, financial sign and posting semantics where applicable, and reconciliation totals. Review and approve the contract separately for each resource type. Then build source-contract-specific staging, row-level review, exact fingerprint and idempotent controlled commit with regression tests. Until these inputs exist, provider-specific imports remain BLOCKED. Do not infer source identity rules from arbitrary CSV column labels or pretend an inspection is an approved import.
