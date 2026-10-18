# PHASE 4.16 — RENTMANAGER MIGRATION FOUNDATION

Status: **NEXT PHASE — CONTRACT-GATED IMPLEMENTATION** (October 17, 2026)

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
