# Yardi Phase 4.15: durable identity entity-type guard

Checkpoint: 2026-10-14. On the sole authorized branch, the preceding SHA 5902362a46e198fce4dea3686f7d2527fb7afa9c passed all six CI jobs in run 38520294815.

The run-level read-only reconciliation previously compared a reviewed target numeric ID and exact source fingerprint with its durable same-run mapping but did not verify target entity type. Every resource requires its expected typed identity: PROPERTIES -> PROPERTY, UNITS -> UNIT, OWNERS -> OWNER_USER, VENDORS -> VENDOR, TENANTS -> TENANT_USER. Conflicts appear as needs_review and invalidate the review fingerprint, without customer mutation. Backend regression verifies wrong durable Unit entity classification reduces matched readiness and restoration reestablishes it. Follow up with exact-SHA six-job CI, handoff verification and further bounded Phase 4.15 implementation.

No unverified official Yardi API, financial posting, lease creation, occupancy update or automatic source merging is enabled.
