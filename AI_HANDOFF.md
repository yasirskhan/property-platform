# AI_HANDOFF.md — Property Platform, 2026-09-28

**READ THIS WHOLE FILE FIRST.** This is the repo-ROOT authoritative session handoff;
it does NOT belong under docs/. Refresh after every meaningful CI-verified batch.
Do not ask Yasir to repeat verified state. Never paste real tax secrets/TINs.

- Private repository: `yasirskhan/property-platform`
- ONLY working branch: `chatgpt/checkpoint-005-safety`. Do not edit `main`,
  create a branch, force-push, or merge the draft PR without permission.
- Last VERIFIED **product source**: `711800ce4d02aa5c1e52f5703b8817740832c24e`
- Source GitHub Actions run **36439808118: SUCCESS, all six jobs** (backend,
  frontend, platform-admin, security, authenticated E2E, staging-config).
  Backend: **711 passed, 3 deselected, 15400 warnings in 182.75s**.
  E2E: **3 passed in 9.57s**. Lint, typecheck, production build, security
  and staging: SUCCESS. These counts apply to this exact source commit only.
  This handoff update itself is docs-only; TESTS NOT RUN locally. Verify
  current branch HEAD and latest CI before continuing.
- Alembic head: **e9a1b3c5d7f0**. SQLAlchemy expected model tables: **134**.
  Previous head d8f0a2b4c6e9 / 133 tables (staff ARC intake adds one table). PostgreSQL/bootstrap/legacy CI passed.
- Phase 3.7 Reports + Universal Attachments: IN PROGRESS.
  **Latest verified batch: Phase 4.7 C2 scoped staff ARC project-intake backend/UI, verified by CI.**
- **1099 Phase 3.7 internal preparation/security is VERIFIED through local preflight,
  NEC/MISC sandbox payload mapping, explicit consent, redacted status/history and
  no-submission guarantees. Actual external sandbox acceptance requires operator
  Avalara subscription/credentials/issuer; production filing/IRS acceptance and
  recipient copies remain NOT IMPLEMENTED and belong to the external provider path.**
- **Exact NEXT task: Phase 4.7 C2 governing-document evidence and applicable jurisdiction/rule review for formal HOA violations, ARC decisions, reserve studies and accounting. No official applications, approvals, notices, penalties, board actions or reserve postings without source authority. Staff observations, meeting planning and ARC staff intake are verified. No payer designation, GL or tenant charge. Phase 4.6 substantive HUD/LIHTC legal, household, AMI and HAP workflows are still BLOCKED on authoritative jurisdiction/program rules and secure household policy; do not mark Phase 4.6 complete or infer eligibility from staff evidence.** Leasing CRM/Prospects, Guest Cards, and source/stage breakdown are VERIFIED. Do not call recorded stages verified applications, marketing conversions, ad ROI, or infer utility charges from bills. No external Stripe/IRS filing integration yet.
  Tenant Delinquency, Security Deposit Funds Detail, Tenant Directory, Tenant Ledger, Tenant Tickler, Tenant Unpaid Charges and Unpaid Charges Summary, plus Owner Packets VERIFIED. Do not repeat verified preflight,
  manual review, register, revision guards, tax profiles or W-9 archive.

## Verification chronology — don't reimplement

| Batch | Source commits | Last full SUCCESS CI | Evidence |
| --- | --- | --- | --- |
| Phase 4.7 HOA property/association registry + customer Compliance UI | d929d71c50b40849e0f5fa6849b294ca87a4780b, 38dee8344851cac33b1f792e16a529211db86782 | 36425025893 | 692 backend passed / 3 E2E; 129 tables; no HOA financial posting |
| Phase 4.7 HOA contact references + customer UI | 404e6dcccff779c63311018221544d8508d929ff, 8b25ab6240c7cd69c1708d28002f583b526af71c | 36426366891 | 694 backend passed / 3 E2E; 130 tables; no dues or payer designation |
| Universal Attachments | 90e54eb834047038f01959c5a2a20c9e4155e999 | 36219990832 | VERFIED |
| Standard/enhanced reports framework | 3afb0d3d2b41a222225e5ca20fb9c976fee77742 | 36221727596 | VERIFIED |
| Shared Print / Email / CSV delivery | f5c8a5177db003c5d6d1b2eb2fbf8510791d31d6, fad5066aa2bc4498156179fad6bb5c8ad1cfcf65 | 36222494517 | VERIFIED |
| Custom Report Builder saved configurations | 5f235e3bdc098885965c227a68956b69ea5f5307, b70be63af5195fe88f7bcadf2d6599732d24ce59, cf6f9aa1a54d276200c310f3b3d8f870cad64e97 | 36246789775 | 383 backend passed / 3 E2E |
| Labels Report CSV mail merge | 02641ebab30e24880b5ab61194f20ad8f0aea2cc, 5a2ee8acc5ea9dc81b4a48ec6d043879b6a7b5df | 36248197021 | 389 backend passed / 3 E2E |
| 1099 IRIS modernization + encrypted tax profiles | 3aca0f64b1f58e8bb7afef32ae6ceda368dbc9ca | 36249130022 | 395 backend passed / 3 E2E |
| Admin 1099 readiness + notes/attachments protection | 5a22b59ed0f3d0c8b877c8b038c5ac2fe67bbeea, caaca02d519cc3c3b47edfc734ec2c705e0cadb2, 488b6b93a00df9788eaaf90d7c9f07b2eb5f1b41, 788010f4b1c3609fb74a98b6bf48b0f037bc4bad | 36249841377 | 400 backend passed / 3 E2E |
| Encrypted signed-paper W-9 archive backend | 18f024a0a1d932f6c2b327c38b2954c6930cd356 | 36250903803 | 406 backend passed / 3 E2E |
| Admin W-9 upload/list/download UI | fe0a7cd39a22a60f4378db50ad85583c8bc45bfc | 36251266775 | 406 backend passed / 3 E2E |
| Sentry request-body and stack-local exclusion | e8552318fcbd85663c678acb0d8f2948f6ebdecb | 36251597787 | 407 backend passed / 3 E2E |
| Bounded ciphertext key rotation | 10eff9806ce1890afadb04afb62ad7849d45258b | 36251944098 | 409 backend passed / 3 E2E |
| Manual NEC/MISC preparation, review and approval | 1ac7a5a6ef2949e0a905f4b354cbb3a80eb63551, 935d24002ee0d9568dd6434948d4a42360302a88, 8fbb07afc1d95ab22eea7a5bb8d7d05e141acb82 | 36266540061 | 416 backend passed / 3 E2E |
| Internal redacted 1099 register | 4a96cd00d098dd82b646dc0e7bc00dc2c4cd3a87, f68e06169b4b8c33f335e97d84dfa00034493c33 | 36267589323 | 418 backend passed / 3 E2E |
| Substantive tax-profile revision and approval staleness guard | 48dc20d6d52d163954cc00956714090d3d2dcae9 | 36268034674 | 423 backend passed / 3 E2E |
| Redacted provider-handoff preflight without submission | 329e106709457647adb8b160a13d44695c102fd3 | 36268470769 | 426 backend passed / 3 E2E |
| Source-text redaction + competing approval guard | 53c26c97c8a6f7f1a4ed16014eb9c80e68ca04f8, 6aa0a0414341d1a7cfc90fa3fcb119beb470f4e7 | 36269106237 | 428 backend passed / 3 E2E |
| Avalara sandbox dry-run adapter | 85a6180a9fce3258d2bda90e878cfb30d4a891ec | 36270582328 | 431 backend passed / 3 E2E |
| Provider status + explicit sandbox UI | 4a54c602966a795a8b399893f3d5fc46a6324ab3 | 36270979448 | 432 backend passed / 3 E2E |
| Avalara 1099-MISC rents sandbox mapping | 49dd9e5129df94e3721f3a97caa0415738bc24bb | 36271476212 | 432 backend passed / 3 E2E |
| Immutable redacted provider dry-run history | 1560b0ec2c436ad363bf6c742036aaf94fd6892e | 36271931432 | 433 backend passed / 3 E2E |
| Letters backend: scoped templates, text merge, reviewed notice send | 0afaec13accb9594d782cd088feca2ef5f92c927 | 36273058209 | 438 backend passed / 3 E2E |
| Letters UI + preview/email digest binding | a896605e16a37d5c5d778043545997b828ab8c7a, 5d9b4142275cdb759ca2701cd1f567f776616100 | 36273560029 | 440 backend passed / 3 E2E |
| Tenant Tickler | f97b2c9c4078076ebd3c1d19d7107068bf49bb42 | 36277065122 | 467 backend passed / 3 E2E |
| Tenant Unpaid Charges | 26cc939f0ca39eb7219b3dad6c3ce4b527ff9a9b | 36277862050 | 471 backend passed / 3 E2E |
| Tenant Unpaid Charges Summary | 1f901348d89fd173794edf651b0a143b63f5dc05 | 36278186270 | 474 backend passed / 3 E2E |
| Property Budget Comparison | 21378853fb7d7ccf31f5b62dadbccf9367e36266, c5dbc67374ebcf7d31f7b6f9ff086af47c6e50b9 | 36278686191 | 478 backend passed / 3 E2E |
| Property Budget Detail | 6b4805ee1ff99d7340026ac5322e03a58408df70 | 36279106102 | 481 backend passed / 3 E2E |
| Property Gross Potential Rent (read-only) | cb85f82c55090450798b5ef3fb941dc9bd97538b | 36279627346 | 485 backend passed / 3 E2E |
| Lease Expiration Detail / Monthly Summary | 08fb55bb470e94e1422cd6b601a28794151c1f46, d818dfbb5652c3f2d0735fa1b891a59c3be38ee2 | 36280075299 | 489 backend passed / 3 E2E |
| Property Directory | 992c949d2ae079f424a8f16bbb8fa131cadf1048 | 36280429259 | 492 backend passed / 3 E2E |
| Property Group Directory | b246d698b2da335796f9aca58ca4d067fb939cc0, 70900226383d4421193ca8f7c76da465369e01f9 | 36280886202 | 496 backend passed / 3 E2E |
| Property Performance | 5c3149c27398b2c321062263795149a594ff63ab | 36283808654 | 499 backend passed / 3 E2E |
| Rent Roll | 8636280f378db4eda2679fee75e699bae139222a, 47fddcdd761fcc434c8e8b60afca87d31800e4f0 | 36284240929 | 502 backend passed / 3 E2E |
| Unit Directory | c1f47e197a8934634b88c77d5a04f0c97609c3a7, a608b1b2e86f2378df825c53d864413c2139197a | 36284770912 | 505 backend passed / 3 E2E |
| Unit Inspection | deb6019ab889c03e8ce5a208da271cb16e16d2a5, 52369dd6ae3237fa4695d1407750c18a3847959e | 36285989151 | 509 backend passed / 3 E2E |
| Unit Vacancy Detail | e61115fd1d0a544c7cddbfd0d8e22df6054ee8da, 0567aa87b894baf41238b61838566b71bc885a9b | 36286373738 | 512 backend passed / 3 E2E |
| Owner Directory | 22bc827577e960a1e4a66203bebe14b7638df58c, 96d731902ac3b3126ab8d93f7d4881a551795609, 05c8e4e73a9e4c93088ddf2773318179dfd0b592 | 36287053275 | 515 backend passed / 3 E2E |
| Tenant Ledger current balances and Charges authorization | a12e0f1af94b7e74e03e9e81988bba98d98cb016, 33902846eab82304299f383001de682081091eec | 36276682654 | 463 backend passed / 3 E2E |
| Tenant Directory | 873219e0be9e41a7c68ec52e4da604a882dc90c2 | 36275843531 | 458 backend passed / 3 E2E |
| Security Deposit Funds Detail GL liability report | 60ee5a986d670b4e3af18d01060e971c163c522f | 36275464600 | 454 backend passed / 3 E2E |
| Owner Packet frozen CSV backend + customer UI | 563596a7baf15ef3e8d5e46c8b8f71f2de29e47a, e170aeba1aa725d8d3c3c2a5c536351dcdc3386b, 2ff688a0c9b20a31cc2cf0ca39b886a8b565cc0f | 36274518298 | 446 backend passed / 3 E2E |
| Vendor Directory (registered contact users) | 840a10ef8d4ecb791b24cb2ef09952f09b2c5cc7, 74fc8455d63d6dac52374ea74e3a8668aba58e71 | 36287404716 | 518 backend passed / 3 E2E |
| Vendor Ledger (linked bill register) | fe0f0d44e129cb5dd21e7b6a0ea7d0b434e8fbed | 36300269360 | 522 backend passed / 3 E2E |
| Work Order recorded summary | ecf5d652e0ec9ca2b0428934446e1073b8d6a629 | 36300632574 | 526 backend passed / 3 E2E |
| Accounting Account Totals | 63c9272670d7eb2b4b509fbec70da681bbfd9767 | 36300974942 | 529 backend passed / 3 E2E |
| Accounting Balance Sheet | 0d8f40db185126be26a67db32dbaa9126d02c782 | 36301335972 | 532 backend passed / 3 E2E |
| Bank Account Activity (posted cash-GL book activity) | d90102a7cd1baa0ae71ff0dace48d70f6357c1dc | 36301725230 attempt 2 | 535 backend passed / 3 E2E; first E2E login-navigation timeout retried successfully |
| Bank Account Association (bank-to-GL mapping, no private bank numbers) | 369f1e3f374397ca704219aa8995b5c5a0ffc159, 73873fddb7fcf7aee7115d6de0d145fbb8d55ad9 | 36323294362 | 538 backend passed / 3 E2E |
| Cash Flow (posted bank-mapped book movement, not GAAP-classified) | 0bce280bcd932b5ba1862689d14380ad620697fb, 5305d8d4cd6c80f7ecb5cf893dbbfe100c3f1b0f | 36323986765 | 541 backend passed / 3 E2E |
| Cash Flow 12-Month with year rollover and earliest-date boundary | c1f97d1823c14a268d7f42263b379cb1f801263c, d4b180fafd06f01b10b64c230184357f1a403881, 0718264d01661140e592ad9008117b2c87740d1b | 36324425667 | 545 backend passed / 3 E2E |
| Expense Distribution (posted accrual expense GL) | 67d8630f871e26226e8a280913742a4ae780d4c4 | 36324862669 | 548 backend passed / 3 E2E |
| Income Statement (posted accrual P&L) | c20ef1877bcde6b5c97da302e25e4767a7f07586 | 36326806250 | 551 backend passed / 3 E2E |
| Trust Account Balance (mapped posted cash GL snapshot) | 6c8ced27805a63e0ad715fac8eb46621c3c58c5a, 9bd8e948d68dad97dd409ca11a7e0f95d3bf0443 | 36327401270 | 554 backend passed / 3 E2E |
| Trust Account Detail (posted trust bank GL entries, validated tags) | 28a697be8317f2754262881f0a3ce6efa4693693 | 36327838434 | 557 backend passed / 3 E2E |
| Aged Payables (posted bill current due aging) | 2558a0b11ab73463071de83c83e6d80aa94ecba2, 895857091f918293761e39d6cb9fad12655fb5e0 | 36328376671 | 560 backend passed / 3 E2E; test-only bucket correction |
| Aged Receivables (current rent invoice due aging) | 7af730729cd126b61331caf0b170b7e290eee0c9, d1e2b0501602c33d61a9c901791286eef6a771cd, 545894bbe5f6acbef78a5b37ee58c707f55f5a81 | 36329631501 | 563 backend passed / 3 E2E; test-only second-property bucket correction |
| Bill Detail (posted bill header and verified lines) | bed121f5796aedd3c6985f5bda972e8dded32d45 | 36330083012 | 566 backend passed / 3 E2E |
| Charge Detail (standalone charges incl paid/credit) | cc0d81971de51bf6b7c0b3cb3d0963b085514e8b | 36330600066 | 569 backend passed / 3 E2E |
| Check Register (issue/void, bank-safe) | 1597120b55d45a37d17bc1baddf4c663abaec4b2 | 36331055801 | 572 backend passed / 3 E2E |
| Check Register Detail (recorded allocations) | 9a1dd5dc941bb4a1043b7c367c072f3d4a54d61e, 0494f6a14bc8ee835837d87c5832995609b52c8f | 36332054459 | 575 backend passed / 3 E2E; first registration CI red corrected |
| Deposit Register (recorded receipt grouping) | bdf317cc8e2912061b1544229303aef12a1d3d34 | 36332538763 | 578 backend passed / 3 E2E |
| Expense Register (posted expense GL detail) | fa8ab2e287aea400e6e684205cf5c9a6308ef85a, 7882a5921be2d38601f0a989d8d46552089debe1 | 36333373605 | Verified source; see subsequent section |
| Income Register (posted income GL detail) | 3875ef5af74097f93643d6925eb8b14dfd6ac147 | 36335844931 | 584 backend passed / 3 E2E |
| Journal Entry Register (manual/recurring JE and linked reversal line report) | 329a85e1683f4392568f8d746404bec689c9b788 | 36336312154 | 587 backend passed / 3 E2E |
| Phase 4.5 RUBs shared utility inventory + period completeness | ca07e0af4103b55425b26561641728f521b991ab | 36367397250 | 644 backend passed / 3 E2E; read-only |
| Phase 4.5 RUBs duplicate/overlap review diagnostics | 54ad71a8ab2d2bb8aaeeaad27f97614707b71369 | 36368986607 | 646 backend passed / 3 E2E; no charges or allocations |
| Phase 4.5 trust-interest manual policy readiness backend | ed9d2d97cce994909798c6f413e2ed4b4247c116 | 36369555961 | 649 backend passed / 3 E2E; no GL posting |
| Phase 4.5 bank trust-interest review UI | a2da32a884a16ff9a1fa8adedc3b199810d19e36 | 36370090346 | 650 backend passed / 3 E2E; no interest posting |
| Phase 4.5 positive-pay issue/void preflight | 82844c94fad5d4ef7fd33ac2e0366055953320e1 | 36370656288 | 653 backend passed / 3 E2E; not a bank upload file |
| Phase 4.5 positive-pay customer bank review UI | 6fe873dfa466a33b478dc638c0196bbddb64c9e5 | 36371943676 | 654 backend passed / 3 E2E; read-only, no bank file |
| Phase 4.6 property-level affordable program inventory | 8c20d48deab2ad5fdbe8c323d8409462bce77068 | 36372554518 | 657 backend passed / 3 E2E; no eligibility determination |
| Phase 4.6 staff-recorded CRM program interest register | 67d4d5f15d10b0830a02702b453c68a98e5e9d45 | 36373217097 | 660 backend passed / 3 E2E; no official ranked waitlist |
| Phase 4.6 scoped affordable evidence-readiness checklist | e492a46356bc19a57c55f63fe9ad85a5e0b7d5c8 | 36378052654 | 665 backend passed / 3 E2E; 123 tables |
| Phase 4.6 read-only recorded unit-inspection cross-reference | 87c2eaa9ba5a21f8cc461c92cf46aaf474cd8b46 | 36378605760 | 667 backend passed / 3 E2E; no migration |
| Phase 4.6 BIN syntax normalization and alias collisions | 6ae01cc927264273e5fc8d067da15bd6c45f3faa | 36379842520 | all six jobs success; 2/4-digit year + five-digit sequence; no new migration |
| Phase 4.6 per-building annual Form 8609-A staff reference tracking | 5b520d93aaa7a4307fb5e8533da552aea210cffd | 36383794588 | 681 backend passed / 3 E2E; 127 tables, no IRS filing |
| Phase 4.6 bounded encrypted compliance document rewrap | 40317c96f7b564abce3483b088727c25c53a6b2b | 36384377433 | All six CI jobs success; previous key support, no migration |
| Phase 4.6 scoped rotation readiness preview | 8c5e2a0973b40e414a68f2b8242621324f0e1419, a8adc7dc2f47a40085c1203b38dd2254d778a907 | 36412399420 | 685 backend passed / 3 E2E; read-only, 127 tables |
| Phase 4.6 administrator rotation-readiness UI | 82c8ede338b9030acfd993bbe6888eae7e07ddce | 36413219901 | 686 backend passed / 3 E2E; existing archive UI; no migration |
| Phase 4.6 staff public agency guidance provenance | 3f2d5d4b60f9eb29ced0aa68c182e41fe51df0e1, d5b63d0310b008489cb645e9d1cc74ab16ea4245 | 36414139582 | 688 backend passed / 3 E2E; 127 tables, no agency validation |
| Phase 4.6 restricted encrypted Form 8609 staff-scan archive | fb448c7b283d1e29950fe1290c5d9c70ca25d51f | 36383165892 | 678 backend passed / 3 E2E; dedicated key, 126 tables |
| Phase 4.6 per-building staff Form 8609 reference readiness | a28a4dd6b46757a226ce5e8ecd683341b1e9502b, 8a480d05e21a842b1376b1f4d5e595fe58d687de | 36382487436 | 674 backend passed / 3 E2E; 125 tables; test-only org-admin scope correction |
| Phase 4.6 staff-recorded LIHTC building BIN inventory | 952261b3448400dc5c4d1742e5b4b70538c1e2af | 36379299678 | 670 backend passed / 3 E2E; 124 tables |
| Phase 4 vendor company entity + scoped customer UI | 6e1d0eb730a71d913021b590667123ee047c4858 | 36336927654 | 590 backend passed / 3 E2E |
| Phase 4 vendor insurance lifecycle | 8d2cb6adffbde41282fc77e9e0365b2913410f66, 3de4c938e07fc695cf33eec3b1a7af7fd552e73b, 5dcdd6272bd1e18fe78a0ae2868ef6d110caf2c8 | 36337623891 | 593 backend passed / 3 E2E |
| Phase 4 vendor trade/insurance filters | b40d94b3861809d4cfd5bb563a21bd6a4e524476, 0d32310911be49c9133ba002d19fdfdb9fce7e9a, 87ed9dd1396686065c9596622173297628b2ace2 | 36338819609 | 596 backend passed / 3 E2E |
| Phase 4 explicit Bill Vendor FK and customer picker | 7a8d30733480a31fb476391a923759d92242c043, 5064b41a2f996d783fd25346a476c0a55c1b4a5a | 36339328334 | 599 backend passed / 3 E2E |
| Phase 4 WorkOrder explicit Vendor FK and staff selector | c14e3c7d0a8a08257e9177247c56a7d1093424fd, b90fd3deab170009e5b577f90f085ff98e034630 | 36339917953 | 601 backend passed / 3 E2E |
| Phase 4 independent Contacts directory and customer CRUD | b91ec3c38055272ae97a81a2e16630e87cd98ac7, be1d1f84cac32a136202e8e17651161a63316fd3, a607c8c370fa42f44e897a34a7667dd46c30ce69 | 36340860778 | 604 backend passed / 3 E2E; fixed existing async toggle E2E race |
| Universal Tags (org-scoped definitions and authorized entity links) | 73d4cceae74c44b1fd45afe18368cd7514706039 | 36341415211 | 607 backend passed / 3 E2E |
| Contacts CSV preview, bounded confirmed import and safe export | 0062cc22834129c1998c2320e5f78cad50b9d1c8 | 36347187712 | 612 backend passed / 3 E2E |
| Rental Applications safe applicant drafts, pending-payment submission and scoped staff queue | 864bf2e02a80e1b2a4af58a0bdaa279b5f4f14a9 | 36347804741 | 617 backend passed / 3 E2E |
| Encrypted applicant address and income questionnaire | cbcc52bf710791abd721b8a63dc4bceb10c9b806 | 36348392919 | 623 backend passed / 3 E2E |
| Read-only server-authorized unit application fee quote + applicant UI | 8e751bed878d158501754ae3858f1047e39888ef | 36359893698 | 626 backend passed, 3 deselected / 3 E2E |
| Applicant idempotent fee preparation with immutable unit fee snapshot (no charge) | af94f8afefd853a906c9bf19fc96819eab42c7fc | 36360330500 | 629 backend passed, 3 deselected / 3 E2E |
| Tenant delinquency live overdue rent invoices | 8a6a27ef3c248e394546bdb4e8a65c8ffa43e6b7, a644bd803787d3ffc9be36de4318a67915248364 | 36274961962 | 450 backend passed / 3 E2E |


All listed full CI runs were successful. Older superseded CI runs may be
CANCELLED, not necessarily failed. Do not transfer test totals to later code.

## Existing verified design contracts

1. Hybrid Capability Gating separates release gate, plan entitlement, org
   configuration, role/menu permission and user preference; backend decides.
   Do not add unrelated per-field flags.
2. Keep all accounting changes on the central immutable GL and respect locked
   periods, idempotency, org/owner/property scope and immutable audit.
   Reporting basis ACCRUAL (default) vs CASH changes reports, not GL.
3. Customer JWT/identity and platform-admin JWT/identity stay separate.
4. Universal notes/attachments are the shared services for ordinary business
   entities; do not create parallel generic storage. Their resolver expressly
   FORBIDS `tax_profiles` and `tax_w9_documents`. They are not safe for
   W-9 content uploaded under another entity name either.
5. Canonical report catalog under REPORTING.ALL, standard BUTTON and enhanced
   TAB, shared ReportActions, server rerendered CSV/email, report-level
   permissions + release.reporting.export gate, CSV formula escaping and
   org scope remain intact. Saved configurations belong to creator and
   organization, with permission rechecks. No arbitrary SQL/report builder.
6. Do not represent planning parity/status as behavioral test evidence.
   Last reported parity metadata before 1099 modernization was
   628 total / 264 built / 364 scheduled / 0 in progress; counts and
   status NOT updated since. `reporting.1099` remains SCHEDULED.

## 1099 modernization and exactly what is implemented

User expressly authorized 2026-09-26 IRIS / approved-provider route instead
of obsolete FIRE and bringing secure W-9/tax profiles into Phase 3.7.
ONLY the 1099 requirement wording in frozen docs/PROJECT_MASTER.md,
docs/PLAN_GAPS.md and docs/APPFOLIO_PARITY_CHECKLIST.json was updated
at 3aca0f64. ALL other docs/ source-of-truth content remains frozen and
must NOT be modified without separate authorization.

**Taxpayer profiles**:
- `backend/app/models/tax_profile.py`, `services/tax_profiles.py`,
  `schemas/tax_profile.py`, `routers/tax_profiles.py`.
- `GET/PUT /api/reporting/tax-profiles`: org-specific ADMIN plus
  REPORTING.ALL, active/not-deleted, actual role/same-org recipient.
- Typed payer ORGANIZATION and OWNER/VENDOR recipient, validated tax ID,
  classification, legal name, business name, mailing address encrypted
  as one Fernet payload. Only masked TIN last four and W-9 status/date
  in output. Audit excludes taxpayer identifiers and mailing contents.
  No data in generic reporting actions or raw field exports.
- No default tax key. `TAX_PROFILE_ENCRYPTION_KEY` must be externally
  provisioned, independent of ordinary `ENCRYPTION_KEY`; fail closed
  with 503 when absent. A live operator must configure it in their
  secret manager, not in source or chat.

**Signed-paper W-9 archive**:
- `backend/app/models/tax_w9_document.py`, migration
  `d6a8b0c2e4f7_add_tax_w9_archive.py`,
  `services/tax_w9.py`, `routers/tax_w9.py`, `schemas/tax_w9.py`,
  `backend/tests/test_tax_w9.py`.
- `GET/POST /api/reporting/tax-w9/{profile_id}` and
  `GET /api/reporting/tax-w9/{profile_id}/{document_id}/download`.
- Raw `application/pdf` streaming, max 5MB, PDF marker/EOF checks,
  no multipart temp-file spool. Encrypted PDF ciphertext in the
  `tax_w9_documents` database table, never unencrypted general
  attachment storage. No-store, forced download, `nosniff`, sandbox CSP,
  org/user/role/REPORTING.ALL scope and audit (archive, metadata list,
  download). Staff attests paper signature review; NOT e-signature,
  signature OCR, PDF antivirus screening or a filing system.
- Page `frontend/src/app/dashboard/reporting/1099/page.tsx` embeds
  `TaxW9Archive.tsx`: secure upload/list/download and paper-W-9
  status, masked taxpayer profile intake, clearly says filing disabled.
  Backend code does not generate IRS filing or recipient copies.
- `TAX_PROFILE_PREVIOUS_KEYS_JSON` (secret manager JSON list, default [])
  permits decrypting older profiles/documents while current key encrypts
  new data. Bounded `POST /api/reporting/tax-profiles/rotate-encryption`
  rewraps up to ten profiles + ten PDFs per call, uses cursors, is org
  and admin scoped, audited without decrypted content, rolls back on
  corruption/missing historical key. See `services/tax_key_rotation.py`,
  `schemas/tax_rotation.py`, tests.
- `app/core/observability.py`: Sentry does not collect HTTP bodies
  (`max_request_body_size="never"`) or exception frame locals,
  `send_default_pii=False`, with regression test. This is not a
  substitute for W-9 PDF malware scanning or complete DLP.

**Manually sourced 1099 preparation, review, approval (VERIFIED)**:
- Migration `e7b9c1d3f5a8_add_tax_1099_reviews.py` adds one
  `tax_1099_reviews` table; SQLAlchemy 103 tables. Backend services
  `app/services/tax_1099_reviews.py`, router
  `app/routers/tax_1099_reviews.py`; frontend
  `components/reporting/Tax1099ReviewPanel.tsx` on Reports > 1099.
- Supports explicit tax-year 1099-NEC nonemployee compensation VENDOR,
  1099-MISC rents OWNER, organization payer plus matching recipient
  encrypted tax profiles, user-entered positive amounts, documented
  source/type/reference. Does NOT infer tax amounts from GL, bills,
  checks, payees or owner payouts; admin checks threshold and exceptions.
- PREPARED -> REVIEWED (requires encrypted archived signed W-9) ->
  APPROVED (three explicit human confirmations); approved records lock.
  Scoped ADMIN/REPORTING.ALL, cross-org isolation, redacted last-four
  TIN output, append-only audit, idempotency key fingerprint,
  no-store, deliberately no filing endpoint. 7 focused backend tests
  and E2E smoke coverage. Earlier 935d2400 test-only scope correction
  passed CI. Full source 8fbb07af had CI 36266540061 SUCCESS.
- An approved record currently references mutable live taxpayer
  profiles: a later tax-profile replacement can change live last-four
  data while its review still says APPROVED. NEXT: add explicit
  profile-revision review/approval invalidation. Do not silently allow
  changed taxpayer data to inherit old approval; key rotation must
  NOT count as a substantive profile change.

**Redacted internal 1099 register (VERIFIED)**:
- Source 4a96cd00d098dd82b646dc0e7bc00dc2c4cd3a87,
  test-only fix f68e06169b4b8c33f335e97d84dfa00034493c33;
  CI 36267589323 SUCCESS all six jobs (418 backend passed,
  3 deselected, 3993 warnings in 79.47s; E2E 3 passed in 7.09s).
- `GET /api/reporting/tax-1099-reviews/register.csv?tax_year=2026`
  uses the verified `ReportPayload` / `report_csv_bytes` renderer.
  ADMIN/REPORTING.ALL plus release.reporting.export required, full
  live-org scope, encrypted profile access, audit of download metadata
  without tax IDs, no-store, nosniff, CSV formula escaping.
  No names/addresses/raw TINs/source notes; last-four masked.
  Includes review status and source reference; every data row says
  "NOT FOR IRS SUBMISSION", filename `1099-internal-review-not-for-irs-<year>.csv`.
  Frontend has an explicit internal CSV download, never a file action.
  New tests prove cross-org exclusion, formula escaping, audit,
  export-gate revocation and 2020-2100 year validation.
- NO filing submission, IRS/IRIS/provider schema, recipient copy or
  state filing is generated. Docs/ other than ROOT HANDOFF unmodified.

**1099 approval integrity safeguard (VERIFIED)**:
- Source `48dc20d6d52d163954cc00956714090d3d2dcae9`,
  CI 36268034674 SUCCESS six jobs, 423 backend passed, 3 deselected,
  4189 warnings in 66.98s; E2E 3 passed in 10.43s.
  Migration `f8c0d2e4a6b9_tax_profile_review_revisions.py` adds
  `tax_profiles.profile_revision` and per-review payer/recipient revision
  snapshots, head f8c0d2e4a6b9, same 103 model tables.
- Tax-profile substantive changes increment revision; normalized
  identical upserts and ciphertext-only key rotation do NOT. New
  signed-paper W-9 archive evidence increments revision.
- Marking REVIEWED captures current payer/recipient revision. Later
  corrections stale existing REVIEWED/APPROVED records; approval
  refuses stale review with 409 until explicitly re-reviewed.
  Historical APPROVED stays immutable but is visibly stale and
  not eligible for downstream submission. Legacy approved rows with
  missing revision snapshot fail closed rather than inheriting
  approval. Live UI and internal CSV explicitly flag re-review need.
- Tests cover correction before approval, immutable stale approval,
  repeat identical upsert, newer signed W-9, key rotation unchanged,
  and legacy rows; no full TINs stored in approval records or export.
- This remains internal review; no IRS tax return or recipient
  copy was generated. Docs/ unchanged. Product code VERIFIED.
  Source CI is more relevant than handoff-only CI.

**Provider-handoff local preflight — VERIFIED 2026-09-26**:
- Product commit `329e106709457647adb8b160a13d44695c102fd3`,
  all-six-job CI 36268470769 SUCCESS. Backend 426 passed,
  3 deselected, 4305 warnings in 65.25s; E2E 3 passed in 9.29s.
  No migration; Alembic f8c0d2e4a6b9 and 103 model tables.
- Authenticated ADMIN/REPORTING.ALL-scoped
  `GET /api/reporting/tax-1099-reviews/{id}/preflight` rechecks
  APPROVED status, current payer/recipient substantive revisions,
  all manual review attestations, archived signed W-9, payer and
  recipient encrypted-identity completeness, positive documented
  amount/source. It fails closed on cross-org/permission revocation.
- Response returns only record ID, tax year/form, review status,
  redacted blockers, boolean local `ready_for_provider_handoff`,
  `filing_enabled=false`, `submission_status=NOT_SUBMITTED`.
  Never serializes TIN, legal name, mailing address, source notes,
  IRS upload file or fake provider success. No-store response,
  metadata-only append-only audit. Frontend review panel has
  "Check provider prerequisites" and a clear no-filing disclosure.
- Three new tests cover incomplete-vs-ready state after explicit
  reapproval, no raw secrets in response/audit, cross-org/revocation,
  missing W-9 evidence; existing test suites remain green.
- The source reference/note fields are user-entered plaintext.
  Potential accidental full tax-ID entry into source fields and
  multiple competing approved records for one payer/recipient/year
  need additional fail-closed safeguards BEFORE provider integration.
  Next bounded batch should validate/redact such source input and
  flag competing current approved records, with tests.
- IRS IRIS taxpayer portal offers official CSV formatting guidelines
  inside authenticated portal, but no public tax-year-2026 template
  was verified here. NEVER label internal register an IRIS import.
  Original docs/PLAN_GAPS.md C9 reserves actual e-filing, corrections
  and recipient delivery for provider Phase 4.5. Do not falsely
  complete full 1099 or create a provider delivery bypass in 3.7.


**Provider-preflight source safety — VERIFIED 2026-09-26**:
- Product commits `53c26c97c8a6f7f1a4ed16014eb9c80e68ca04f8` and
  `6aa0a0414341d1a7cfc90fa3fcb119beb470f4e7`; CI 36269106237
  SUCCESS all six jobs. Backend 428 passed, 3 deselected, 4398 warnings
  in 84.14s; E2E 3 passed in 9.08s. No migration; head remains
  f8c0d2e4a6b9 and 103 tables.
- New PREPARED/updated source reference/note rejects SSN/EIN-like
  identifiers with a generic 422 message. Existing legacy source text is
  redacted in API/CSV output instead of exposed. Private source validation
  still sees original stored text so preflight fails closed until cleaned.
- Provider preflight blocks a CURRENT APPROVED competing record for the
  same organization/payer/recipient/form/income category/tax year. Stale
  historical approvals remain immutable audit history and are not treated
  as a current competing filing. Nothing is auto-selected or submitted.
- Tests cover new input rejection, legacy redaction, private-source
  validation, current duplicate approval, stale historical approval,
  cross-org/status invariants and existing encryption/revision safeguards.


**Avalara sandbox dry-run provider adapter — VERIFIED 2026-09-26**:
- Product commit `85a6180a9fce3258d2bda90e878cfb30d4a891ec`;
  CI 36270582328 SUCCESS all six jobs. Backend 431 passed,
  3 deselected, 4505 warnings in 84.11s; E2E 3 passed in 8.83s.
  No migration; Alembic f8c0d2e4a6b9, 103 tables.
- Server-only config: TAX_1099_PROVIDER defaults `disabled`; the only
  supported provider mode is `avalara_sandbox`. Client ID, client secret,
  issuer ID and API version are environment secrets/config; no repo defaults.
  Settings refuse a partially configured enabled sandbox provider.
- `POST /api/reporting/tax-1099-reviews/{id}/provider/avalara-sandbox/validate`
  requires ADMIN/REPORTING.ALL and an explicit
  `confirm_external_tax_data_sandbox=true`. Existing local preflight,
  revision, W-9, duplicate-approval and source-safety gates run first.
- Adapter obtains an OAuth client-credentials token from Avalara sandbox and
  calls the official `/1099/forms/$bulk-upsert?dryRun=true` endpoint.
  It forces federalEFile=false, stateEFile=false and postalMail=false;
  no production URLs, filing/scheduling endpoint or recipient delivery.
  API/audit response is redacted and NEVER includes provider response body,
  raw TIN, name, address, token, client secret or source notes.
- Initial adapter commit supported only 1099-NEC. Subsequent verified
  commit 49dd9e5129df94e3721f3a97caa0415738bc24bb added official
  1099-MISC rents mapping. Tests mock all external requests; CI did NOT
  contact Avalara or claim sandbox credentials.
- Official Avalara docs checked 2026-09-26 document an active subscription,
  OAuth client credentials, sandbox token/API URLs and bulk-upsert dryRun.
  A real operator must provision sandbox credentials/issuer before any
  external validation can occur. This is NOT an IRS filing or acceptance.


**Provider status + explicit sandbox validation UI — VERIFIED 2026-09-26**:
- Product commit `4a54c602966a795a8b399893f3d5fc46a6324ab3`;
  CI 36270979448 SUCCESS all six jobs. Backend 432 passed,
  3 deselected, 4531 warnings in 82.97s; E2E 3 passed in 8.59s.
  No migration; Alembic f8c0d2e4a6b9 and 103 model tables.
- `GET /api/reporting/tax-1099-reviews/provider/status` requires live
  tax-admin authorization and exposes only DISABLED vs AVALARA_SANDBOX,
  configured boolean, sandbox_only=true, filing_enabled=false and supported
  forms. It never exposes client ID/secret or issuer ID; no-store response.
- Admin review UI loads the redacted status. After local preflight is ready,
  a configured supported form shows a separate sandbox disclosure checkbox
  and validation button. The admin must explicitly acknowledge that taxpayer
  data will be transmitted to the configured Avalara sandbox for dry-run
  validation. UI explicitly says no federal/state filing, postal mail,
  e-delivery or IRS acceptance occurs.
- Disabled/unconfigured provider or unsupported form shows a no-transmission
  message instead of an action. Current supported mapping remains 1099-NEC.
- Regression test proves status is no-store, permission-scoped and excludes
  all provider secrets. Frontend lint/typecheck/build and full CI green.


**Avalara 1099-MISC rents sandbox mapping — VERIFIED 2026-09-26**:
- Product commit `49dd9e5129df94e3721f3a97caa0415738bc24bb`;
  CI 36271476212 SUCCESS all six jobs. Backend 432 passed,
  3 deselected, 4532 warnings in 87.23s; E2E 3 passed in 9.99s.
  No migration; Alembic f8c0d2e4a6b9 and 103 model tables.
- Avalara's official v2 SDK model documents 1099-MISC `rents` and the
  same bulk-upsert form envelope used by 1099-NEC. The sandbox dry-run
  adapter now supports MISC/RENTS with `rents=<manually reviewed amount>`.
- Provider payload now keeps federalEfileDate, stateEfileDate and
  recipientEdeliveryDate null, postalMail=false, tinMatch=false and
  addressVerification=false. `dryRun=true` remains mandatory.
- Both NEC and MISC are shown as supported by the redacted sandbox status.
  Tests prove MISC uses `rents`, never NEC compensation, never schedules
  delivery/filing, and does not echo provider body/TIN/secret to output/audit.
- Existing deprecated-but-supported Avalara `recipientName` is retained
  because the current verified tax profile stores one legal tax name, not
  structured individual first/last tax-name fields. Do not invent a split.


**Immutable redacted provider dry-run history — VERIFIED 2026-09-26**:
- Product commit `1560b0ec2c436ad363bf6c742036aaf94fd6892e`;
  CI 36271931432 SUCCESS all six jobs. Backend 433 passed,
  3 deselected, 4562 warnings in 63.07s; E2E 3 passed in 8.50s.
  No migration; Alembic f8c0d2e4a6b9 and 103 model tables.
- Existing append-only `audit_log` is the single history store; no duplicate
  provider-attempt table was added. Each provider dry-run audit now stores
  only provider, dry_run=true, HTTP status, validated bool, submitted=false
  and the app-generated correlation UUID.
- Admin no-store endpoint
  `GET /api/reporting/tax-1099-reviews/{id}/provider/attempts` rechecks org/
  tax-admin access and returns only safe parsed audit metadata. Malformed,
  non-dry-run or submitted-looking legacy audit payloads are ignored.
- Review UI loads history after preflight/validation and labels every entry
  NOT SUBMITTED. Provider response bodies, tax IDs, names, addresses,
  credentials, issuer ID and tokens are never persisted/exposed by history.
- External provider boundary: CI uses mocked requests only. A real Avalara
  sandbox validation requires operator-provisioned active subscription,
  sandbox client credentials and issuer ID. Missing those external credentials
  blocks only real provider verification, not continuing Phase 3.7.

**CURRENTLY NOT IMPLEMENTED**: provider-hosted e-W9 consent/signature,
backend PDF malware scanning/retention purge, automatic reportable-payment
identification, official IRS tax-year submission template mapping, live
provider/TCC credentials, real transmission, IRS/provider acceptance receipts,
corrections, recipient copies or e-delivery. Manual NEC/MISC preparation,
review/approval and sandbox request mapping ARE implemented and verified.
Do not claim any unimplemented external filing behavior or enable "file".

## Phase 3.7 Letters backend — VERIFIED 2026-09-26

Product commit 0afaec13accb9594d782cd088feca2ef5f92c927;
CI 36273058209 SUCCESS all six jobs. Backend **438 passed,
3 deselected, 4712 warnings in 87.86s**; E2E **3 passed in 9.08s**.
Frontend lint/typecheck/build, security, platform admin and staging GREEN.
Migration c7e9a1b3d5f2 adds letter_templates; expected 104 tables.
Three schema/bootstrap guards adjusted and passed. Frozen docs/ unchanged.

Backend files: models/letter_template.py, schemas/letter.py,
services/letters.py, routers/letters.py, app/main.py, init_db.py;
catalog now links standard "Letters" to /dashboard/reporting/letters.
Five focused backend tests in tests/test_letters.py validate org isolation,
manager property assignment, inactive/deleted tenant/lease scope,
plain-text tag allowlist/no HTML/no arbitrary expressions, immutable
metadata-only audit, explicit notice legal review, recipient sourced
exclusively from live scoped lease, and rechecked release.reporting.export.
Routes under /api/reporting/letters support list/create/read/update/
deactivate, scoped tenant preview and explicit confirmed email delivery.
Only org ADMIN may modify templates; ADMIN/MANAGER with REPORTING.ALL
and LEASING may preview/email for scoped active leases. Emails reuse
existing core email service. No parallel generic attachment store,
no accounting posting, no legal jurisdiction template fabricated.
3-DAY notice category is an editable draft only; email requires
confirm_recipient, confirm_content_reviewed, confirm_legal_review.
No automatic statutory deadline, proof of service, physical delivery
or legal sufficiency claim.

**NEXT**: customer Letters UI with template overview/editor,
tenant lease picker, live server preview, printable plain text,
explicit email review confirmations and 3-day legal-review disclosure.
Do not mark full Letters VERIFIED until UI CI succeeds. Consider
preview-to-send content revision binding before treating legal
notice workflow as production-safe; current confirmations are
boolean-only and a template might change between preview and send.
No changes to main or frozen docs/.

## Phase 3.7 Letters customer UI — VERIFIED 2026-09-26

Signed preview / send review integrity:
a896605e16a37d5c5d778043545997b828ab8c7a.
Overview/editor/print/email customer page:
5d9b4142275cdb759ca2701cd1f567f776616100.
Final source CI **36273560029 SUCCESS** all six jobs.
Backend **440 passed, 3 deselected, 4788 warnings in 48.62s**;
browser E2E **3 passed in 6.63s**; frontend lint/typecheck/build,
platform-admin, security, staging-config SUCCESS.
Two focused backend tests added to the previous five-letter suite.
No migration in this batch: Alembic c7e9a1b3d5f2, 104 tables.
Handoff-only update TESTS NOT RUN locally. No docs/ changed.

Customer Reports > Mailings > Letters page now:
- Lists org templates; ADMIN can create, view/edit and deactivate
  CUSTOM and THREE_DAY_NOTICE text-only templates.
- User picks an active lease, server checks live org/tenant/property
  assignment and authorization and returns rendered text.
- A preview HMAC tied to requesting staff user, org, template ID,
  lease ID, category, exact rendered subject/body and live recipient
  email is required on email send. Changed content/recipient/lease
  produces HTTP 409 and requires fresh preview/review. Not a legal
  service signature; only review-integrity control.
- Browser offers printable plain-text preview; recipient/content
  confirmations and extra legal-review checkbox for 3-day draft.
  No jurisdiction-specific statutory language/dates or assumption
  that emailing equals valid notice service.
- Email reuses existing core SMTP/console service and writes
  metadata-only immutable audit. Existing REPORTING.ALL + LEASING
  and release.reporting.export gates apply. MANAGER scope uses active
  assigned properties. No arbitrary recipient email accepted.
- Current E2E CI smoke remains 3 existing browser tests; new
  feature-specific coverage is in focused backend regression tests.
  Do not misrepresent those three as dedicated Letters browser tests.

FULL LETTERS ORIGINAL PHASE 3.7 BATCH VERIFIED.
NEXT original-plan task: Send Owner Packets. Preserve verified
owner statement snapshot, owner packet settings, export and email.
External Avalara sandbox/IRS acceptance remains unverified,
not a reason to block owner packet/reporting work.


## Phase 3.7 Send Owner Packets — VERIFIED 2026-09-26

Owner packet backend: commit 563596a7baf15ef3e8d5e46c8b8f71f2de29e47a,
CI 36273951824 SUCCESS all six jobs (445 backend passed,
3 deselected, 4939 warnings in 88.84s; 3 E2E passed in 7.18s).
Customer page and regression tests: e170aeba1aa725d8d3c3c2a5c536351dcdc3386b;
admin-only directory-load scope correction:
2ff688a0c9b20a31cc2cf0ca39b886a8b565cc0f.
Final CI 36274518298 SUCCESS all six jobs:
446 backend passed, 3 deselected, 4969 warnings in 86.94s;
3 E2E passed in 8.51s, frontend lint/typecheck/build,
platform-admin/security/staging-config PASS. No migration.
Alembic c7e9a1b3d5f2 / 104 SQLAlchemy tables unchanged.

Backend /api/accounting/owner-packets/{statement_id}/preview and
/email use frozen OwnerStatement.property_data and existing
ReportPayload/report_csv_bytes; configured OWNER_STATEMENT and/or
PROPERTY_CASH_SUMMARY, selected via existing OwnerPacketSettings.
Only ADMIN or assigned MANAGER with REPORTING.ALL and
ACCOUNTING.OWNER_STATEMENTS, packet-customizer, export and
cash-summary gates may preview/send. Managers require ALL
snapshot properties assigned; other-org owner, deleted/inactive
owner/statement and unsupported settings fail closed.
Recipient email always resolved from the live scoped OWNER user,
not arbitrary client input. A signed HMAC preview binds actor,
organization, statement, owner, recipient, selected CSV content,
email-enabled preference, cover message and subject. Email requires
two explicit confirmed checkboxes and same live preview token;
recipient/config/snapshot changes reject 409. Metadata-only audited
email; no fresh GL posting or recomputation. Attachment format
is CSV, NOT a PDF. Console-mode email remains the normal development
delivery backend, not proof of physical inbox receipt.

UI: /dashboard/accounting/owner-statements/packets, linked from
Reports catalog, Owner Statement detail and Packet Settings.
Shows frozen statement selection, current scoped recipient,
period, cover note, attachment names, CSV-format disclosure,
recipient and snapshot review confirmations, gated send and
success/failure messages. ADMIN loads org statement directory.
MANAGER does NOT request that org-wide directory, uses explicit
statement ID; backend still reauthorizes every preview/email.
Any invalidated preview clears checkboxes and requires fresh review.
Packet Settings old "not yet available" wording corrected.
Focused new backend test covers no-store preview and inactive owner;
existing tests cover cross-org, manager assignment, live email,
HMAC stale changes, entitlement revocation and CSV escaping.
Existing authenticated E2E smoke now visits packet page and
asserts no blind send action. Existing three browser tests remain
three (not three dedicated owner-packet tests).

FULL SEND OWNER PACKETS ORIGINAL PHASE 3.7 BATCH VERIFIED.
NEXT original roadmap Section 38: Tenant Reports, first
Delinquency then Security Deposit Funds Detail, Tenant Directory,
Ledger, Tickler, Unpaid Charges, Summary. Inspect report catalog
and actual invoice/charge/deposit models; preserve balance
accuracy, reporting basis, org/property scope and export gates.


## Phase 3.7 Tenant Delinquency — VERIFIED 2026-09-26

Source 8a6a27ef3c248e394546bdb4e8a65c8ffa43e6b7;
focused test-fixture correction
a644bd803787d3ffc9be36de4318a67915248364.
Final full CI 36274961962 SUCCESS all six jobs:
450 backend passed, 3 deselected, 5190 warnings in 90.27s;
authenticated E2E 3 passed in 7.07s; frontend lint/typecheck/
build, platform admin, security and staging-config success.
The first superseded CI 36274941584 was cancelled after the
fixture correction. No schema migration; Alembic c7e9a1b3d5f2,
104 tables unchanged. No frozen docs/ files modified.

Report catalog enhanced TAB tenant.delinquency now links to
/dashboard/reporting/delinquency. Backend
services/tenant_delinquency.py reports TODAY's overdue rent
invoice balances from recorded RentInvoice.amount_due + late_fee
- amount_paid; excludes due-today/future, VOID and fully paid
balances. Uses live invoice balances ONLY (not a historical-as-of
AR snapshot); distinct unpaid tenant charges are explicitly
excluded and remain a separate roadmap report. No GL writes.
Each row: tenant/property/unit/invoice, due date, days overdue,
rent, late fee, paid and outstanding. Server CSV/email use the
existing authorized ReportPayload/report_csv_bytes renderer.
GET /api/reporting/delinquency/preview is no-store, requires
REPORTING.ALL, LEASING, release.reporting.export, and current
active ADMIN or MANAGER; manager rows restricted to assigned
nondeleted properties, tenants and units org/active scoped.
Optional property_id probing returns same not-found response for
foreign/unassigned properties. Unknown historical-as-of or SQL
filters fail closed. New focused tests cover current balance
math, scope, CSV formula escaping, invalid filters, permission/
export revocation and preview no-store. Existing authenticated
browser smoke now visits Delinquency route; not a dedicated
interactive export E2E test.

Next Section 38 report Security Deposit Funds Detail. Source
evidence: Lease.security_deposit is a contract amount, not proof
funds were held. Existing posted GL liability 2101 and org
owner-held DEPOSIT_LIABILITY Key Accounts can support an
accurate ledger-based detail, but GLEntry may not have a
tenant ID and unallocated property entries must be disclosed.
Do not falsely label contract amount or inferred owner/tenant
attribution as reconciled bank-held cash. Preserve org/manager
scope, reporting and accounting permissions, booked GL
immutability and CSV/export gates; add focused tests.

## Phase 3.7 Security Deposit Funds Detail — VERIFIED 2026-09-26

Source commit 60ee5a986d670b4e3af18d01060e971c163c522f;
CI 36275464600 SUCCESS all six jobs: backend 454 passed,
3 deselected, 5451 warnings in 79.84s; E2E 3 passed in 9.45s;
frontend lint/typecheck/build, security, platform-admin and
staging-config SUCCESS. No migration: Alembic c7e9a1b3d5f2,
104 model tables unchanged. No frozen docs/ changed.

Backend services/security_deposit_funds.py and existing report
catalog/delivery/reporting router supply standard
tenant.security_deposit_funds_detail, Reports > Tenant >
Security Deposit Funds Detail and customer route
/dashboard/reporting/security-deposits. Backend preview:
GET /api/reporting/security-deposits/preview, no-store.
Shared server-generated CSV/email delivery and ReportActions
are reused. Optional posted-through as_of date and property_id.
REPORTING.ALL, ACCOUNTING.GL_ACCOUNTS, release.reporting.export
must authorize each preview/export/email. Service additionally
requires active ADMIN or MANAGER within same organization. Managers
see only nondeleted, actively assigned properties; admins may
review explicitly labeled unallocated entries. Foreign/unassigned
property probes fail closed. Cross-org account/transaction/entry
rows excluded.

Detail is posted GL LIABILITY account 2101 plus configured
DEPOSIT_LIABILITY key accounts only, credit-minus-debit movements.
Original entries and posted reversals BOTH count by business date;
future entries and other GL accounts do not. Includes entry ID,
date, account, reference, property, coherent unit tag, debit/credit,
net movement, allocation warning. No tenant attribution is inferred
from GL entries. No lease contract security_deposit is counted as
cash received. No bank-held cash/reconciliation claim, no GL writes.
Four focused new backend tests cover reversal and date accuracy,
owner-held account inclusion, manager/org isolation, formula-safe
CSV, preview no-store, permission/export revocation and server email.
Existing browser smoke remains 3 general tests, not feature-specific.

NEXT exact original report: Tenant Directory, then Tenant Ledger,
Tickler, Tenant Unpaid Charges and Summary. Preserve tenant
organization and manager-assigned property scope; do not expose
unassigned tenants to managers. Read actual User/Lease/Unit/Property
models before coding. Build only report data and customer view,
reusing existing report permissions, catalog, CSV/email. Add focused
security and CSV tests; commit then CI; update this handoff after
verification.

## Phase 3.7 Tenant Directory — VERIFIED 2026-09-26

Source 873219e0be9e41a7c68ec52e4da604a882dc90c2.
CI 36275843531 SUCCESS six jobs. Backend 458 passed,
3 deselected, 5652 warnings in 90.10s; E2E 3 passed in
9.28s. Frontend lint/typecheck/build, security, platform-admin,
staging-config passed. No migration, head c7e9a1b3d5f2,
104 tables. No frozen docs/ edits.

Standard catalog entry tenant.directory links to
/dashboard/reporting/tenants; read-only preview endpoint
GET /api/reporting/tenants/preview returns no-store. Shared
ReportPayload/CSV/email and ReportActions reused. Report requires
REPORTING.ALL, LEASING, release.reporting.export; active ADMIN
or MANAGER, same org. Managers see only eligible current leases
on their actively assigned properties, not unassigned tenant
contact details. Admin sees all active tenant users, including
those lacking an eligible current lease (clearly labeled) and
current associations, excluding terminated/future and noncurrent
leases, deleted/inactive users/units/properties and foreign orgs.
A tenant with more than one current lease has one association row
per eligible lease. Optional property_id is validated against
live visible properties; other-org/unassigned property probes
fail closed. CSV formula escaping stays server-side.
Four focused backend tests cover isolation, two-property scope,
inactive/future/terminated exclusions, unassigned contacts,
invalid filters, preview no-store, email/CSV and entitlement/
permission revocation. Existing browser E2E smoke remains three
general tests, not dedicated directory tests.

NEXT Tenant Ledger. IMPORTANT: tenant rent invoice payments in
Lease.Payment records and accounting Receipt/ReceiptLine entries
are independent data paths; do not blindly sum both. Charge
amount_paid is a current snapshot, not a dated transaction log.
Investigate real payment/receipt/reversal semantics first and
avoid inventing a historically reconciled running balance or
claiming all payments posted through GL. Securely scope all
tenant/property selection; preserve existing reports/GL.

## Phase 3.7 Tenant Ledger — VERIFIED 2026-09-26

Source a12e0f1af94b7e74e03e9e81988bba98d98cb016,
follow-up security 33902846eab82304299f383001de682081091eec.
First source run 36276282964 SUCCESS: backend 462 passed,
3 deselected; 3 E2E passed. Follow-up source run
36276682654 SUCCESS six jobs: backend 463 passed, 3 deselected,
5898 warnings in 91.44s; E2E 3 passed in 9.50s;
frontend lint/typecheck/build, platform-admin, security and
staging-config passed. Alembic c7e9a1b3d5f2, 104 tables;
no migrations, no frozen docs edits.

Enhanced TAB catalog key tenant.ledger, route
/dashboard/reporting/tenant-ledger and
GET /api/reporting/tenant-ledger/preview (no-store) implement a
CURRENT invoice and standalone-charge balance schedule, not
a historical/reconciled GL ledger. The invoice paid snapshot and
charge paid snapshot are authoritative for their own rows.
Independent Payment and Receipt/ReceiptLine events are not
concatenated because there is no confirmed foreign-key linkage
and doing so could double-count money. VOID invoices excluded.
No invented rent/charge payments or GL postings.
Admin may see same-org historical properties/unallocated charges;
managers are limited to active, nondeleted assigned properties.
Tenant IDs/foreign property filters fail closed. Authenticated
active ADMIN/MANAGER, REPORTING.ALL, LEASING and
release.reporting.export are enforced, with CSV formula escape
and shared email delivery. Follow-up regression requires
ACCOUNTING.CHARGES (matching standalone Charge API permission)
because ledger exposes Charge balances; denial fails closed.
Source tests verify snapshots/no double count, manager/org scope,
bad filters/actor and release/menu revocation plus charge
permission revocation. Current browser E2E remains generic smoke.

Next Tenant Tickler from original Section 38. Original
AppFolio guide defines Tickler as tenant contact information
and most recent event; external reference (check separately):
https://formspal.com/wp-content/uploads/2021/08/appfolio-manager-guide.pdf
Use only actually recorded lease events, tenant/lease notes or
documented milestones; do not invent move-out/notice dates
or claim inferred event activity is a verified external event.
Enforce org/manager assignment and live export permissions.
Then Tenant Unpaid Charges and Unpaid Charges Summary.

## Phase 3.7 Tenant Tickler — VERIFIED 2026-09-26

Source f97b2c9c4078076ebd3c1d19d7107068bf49bb42.
CI 36277065122 SUCCESS all six jobs:
467 backend passed, 3 deselected, 6027 warnings in 92.34s;
3 browser E2E passed in 8.94s.
No migration; Alembic c7e9a1b3d5f2, 104 tables.
No frozen docs/ changes. Scoped tenant contact report takes only
actually recorded lease creation/update/signature/timestamped note
events; does not infer actual move-out/notices from contract dates
or publish private note bodies. Authenticated admin/manager,
manager-assigned live property scope, report/LEASING/export
permissions, standard CSV/email/report page and focused tests.

## Phase 3.7 Tenant Unpaid Charges — VERIFIED 2026-09-26

Source 26cc939f0ca39eb7219b3dad6c3ce4b527ff9a9b.
CI 36277862050 SUCCESS all six jobs:
471 backend passed, 3 deselected, 6212 warnings in 71.33s;
3 browser E2E passed in 9.20s; frontend lint/typecheck/build,
security, platform-admin, staging-config SUCCESS.
No migration; Alembic c7e9a1b3d5f2 / 104 tables.
No frozen docs/ changes.

New standard catalog key tenant.unpaid_charges links to
/dashboard/reporting/unpaid-charges. API
GET /api/reporting/unpaid-charges/preview returns no-store;
server CSV/email via canonical ReportPayload/ReportActions.
Current positive (Charge.amount - Charge.amount_paid) snapshot
from standalone organization-scoped Charge only, NOT rent invoices
or invoice late fees. Fully paid, credit/overpaid, inactive/deleted
and cross-org charges excluded. Recorded charge balances are
not historical account reconciliation or separate GL posting.
Positive propertyless org charges are explicitly labeled for
ADMIN only; managers see only live actively assigned properties.
Active tenant and property scope, tenant_id/property_id probe
guards, REPORTING.ALL, ACCOUNTING.CHARGES and LEASING
permissions plus release.reporting.export gate enforced; CSV
formula escaping. Focused tests include arithmetic/no double
counting, cross-org and manager isolation, foreign filters, denied
roles/permissions, no-store preview, CSV/email/revoked export.
The existing generic three browser smoke tests are NOT dedicated
feature-specific E2E for Unpaid Charges.

NEXT exact original Section 38: Tenant Unpaid Charges Summary
(catalog tenant.summary); aggregate ONLY these same authorized
standalone positive Charge snapshot rows per tenant, reuse service
scope and CSV/email, never mix in rent invoices or assume
GL-reconciled collections. Follow with Property & Unit reports.
Do not skip and do not reimplement verified tenant reports.

## Phase 3.7 Tenant Unpaid Charges Summary — VERIFIED 2026-09-26

Source 1f901348d89fd173794edf651b0a143b63f5dc05.
GitHub CI 36278186270 SUCCESS all six jobs: backend
474 passed, 3 deselected, 6350 warnings in 91.87s;
authenticated E2E 3 passed in 9.20s; frontend lint/typecheck/
production build, security, platform-admin, staging-config GREEN.
No migration, Alembic c7e9a1b3d5f2 / 104 tables unchanged.
Frozen docs/ unchanged. Previous handoff-only CI 36278139301
was CANCELLED by the new product push, not a test failure.

Standard catalog key tenant.summary now visibly titled
"Tenant Unpaid Charges Summary" and links to
/dashboard/reporting/unpaid-charges-summary. GET
/api/reporting/unpaid-charges-summary/preview returns no-store.
Service app/services/tenant_unpaid_summary.py reuses only
already-authorized positive Charge detail report rows,
aggregates by tenant and property (propertyless ADMIN-only
charges separate), computes count/billed/paid/outstanding.
No RentInvoice/GL addition or double counting; current
recorded Charge.amount_paid snapshots, not historical cash.
Admin/manager organization and assigned-property scope,
tenant_id and property_id validation, REPORTING.ALL,
ACCOUNTING.CHARGES, LEASING and release.reporting.export
preserved through shared detailed service/routers.
Server CSV/email canonical formula-safe ReportActions reused.
Three focused tests cover reconciled-to-detail grouping, org and
manager scope, filters, permissions and export gate. Existing three
E2E browser tests generic, not dedicated summary UI tests.

NEXT original Section 38: Property & Unit > Budget Comparison,
then Budget Detail, Gross Potential Rent, Lease Expiration
Detail/Summary, directories and other listed property reports.
REQUIRED RESEARCH: the current backend models inventory has NO
PropertyBudget or other persisted budget baseline; do NOT invent
budget numbers from estimated rent or assume current GL is a
budget. First add an explicitly editable, authorized budget data
source or identify an existing verified one before comparing
actuals, with migration/tests and reporting basis disclosure.
Preserve read-only GL and assignment boundaries.

## Phase 3.7 Property Budget Comparison — VERIFIED 2026-09-26

Product commit 21378853fb7d7ccf31f5b62dadbccf9367e36266;
focused test-only assertion correction
c5dbc67374ebcf7d31f7b6f9ff086af47c6e50b9.
Final CI 36278686191 SUCCESS all six jobs: backend
478 passed / 3 deselected / 6557 warnings in 80.69s;
E2E 3 passed in 7.86s; frontend lint/typecheck/build,
security, platform-admin and staging-config SUCCESS.
Superseded source 36278666804 and prior handoff-only CI
36278523767 CANCELLED, not valid full-green evidence.
Migration b0d2f4a6c8e1 adds property_budget_lines,
105 model tables; PostgreSQL/legacy/fresh bootstrap guards
updated and passed. No unrelated frozen docs/ edits.

Budget target model PropertyBudgetLine is organization/property/
income-or-expense GL-account/year/month-scoped, unique by scope.
No existing budget sources existed, so admin explicitly enters
nonnegative monthly amounts via restricted PUT
/api/reporting/property-budgets. GET lists authorized property/year
targets. Only active org ADMIN may write; active ADMIN/MANAGER with
REPORTING.ALL, PROPERTIES.ALL and ACCOUNTING.GL_ACCOUNTS
may read if current property scope allows; managers need live
assignment. Actor, account, property and org validated.
Budget changes are metadata-audited; never post GL transactions.
Budget Comparison enhanced TAB now links to
/dashboard/reporting/budget-comparison, which has admin budget
entry and read-only comparison, CSV/email via existing ReportActions.
GET /api/reporting/budget-comparison/preview is no-store and
requires normal report/menu/export gates. Source service sums
actual dated, property-tagged posted GL entries, including
original and reversal postings; INCOME actual credit-minus-debit,
EXPENSE debit-minus-credit, positive variance favorable.
Only rows with explicitly configured budget targets are
included; missing target is NOT assumed zero, property estimated
rent is NOT a fabricated budget. CROSS-ORG entries and
out-of-scope properties/accounts are excluded. Comparison
refuses organization CASH-basis setting rather than presenting
accrual GL movements as CASH actuals; only ACCRUAL currently
supported. No historical cash basis or journal modifications.
Focused tests cover budget amount math, income/expense favorable
sign, isolation, manager assignment, invalid account/filters,
CASH refusal, audit, no new GL entries, report preview/CSV/email,
no-store and release/menu revocation. Generic E2E smoke 3,
not dedicated budget interactive tests.

NEXT original Property & Unit task: Budget Detail. Reuse the
new explicit monthly PropertyBudgetLine records and exactly
the same property/account scope, but present an account-wise
12-month detail with unconfigured months blank (not silently zero)
and annual total over recorded months. No posted actuals needed
and no separate budget storage. Then Gross Potential Rent and
lease-expiration reports per original Section 38 order.

## Phase 3.7 Property Budget Detail — VERIFIED 2026-09-26

Source 6b4805ee1ff99d7340026ac5322e03a58408df70.
CI 36279106102 SUCCESS all six jobs: backend 481 passed,
3 deselected, 6715 warnings in 99.70s; browser E2E 3
passed in 8.81s; frontend lint/typecheck/build, security,
platform-admin, staging-config SUCCESS. No new migration:
b0d2f4a6c8e1, 105 model tables. Frozen docs/ unchanged.

Standard Property & Unit report catalog property.budget_detail
links to /dashboard/reporting/budget-detail; backend preview
GET /api/reporting/budget-detail/preview is no-store. Reuses
existing PropertyBudgetLine by org/property/income-or-expense GL
account/calendar year/month; property scope, ADMIN/MANAGER
assignment, REPORTING.ALL / PROPERTIES.ALL /
ACCOUNTING.GL_ACCOUNTS and release.reporting.export gates
rechecked. Each account row shows all 12 months, explicitly
unconfigured blank (not invented zero), recorded zero as zero,
configured annual sum and number of configured months.
No actual GL movements, cash-basis inference, or posting;
budget-only output works for ACCRUAL and CASH.
Existing ReportActions server CSV/email and formula escaping;
three focused regression tests cover blanks/zero/sums, CASH
comparison distinction, org/manager isolation, filters,
permission/release revocation and preview/delivery.
Three generic authenticated browser smoke tests, NOT
three dedicated budget UI tests.

NEXT Gross Potential Rent (GPR) report. IMPORTANT already
VERIFIED app/services/gpr_posting.py implements org-scoped
GPR candidate calculation and posting, keyed to Unit.monthly_rent
(market) and active Lease.monthly_rent (scheduled), plus
loss/gain and posted unit/month marker. The historical candidate
is derived from CURRENT editable unit/lease config, not a frozen
historical rent snapshot; do not claim as-of historical truth.
Post GPR workflow already verified (parity accounting.gl.post_gpr
marked built); do not reimplement posting. Read actual source,
scope manager to live assigned properties BEFORE calling
lease helper, distinguish candidate projected vs posted GPR.
No GL writes in report. Verify what posted source transactions
record and allow reversals, no double count.

## Phase 3.7 Gross Potential Rent report — VERIFIED 2026-09-26

Product commit cb85f82c55090450798b5ef3fb941dc9bd97538b;
CI 36279627346 SUCCESS all six jobs. Backend 485 passed,
3 deselected, 6841 warnings in 86.07s; authenticated E2E
3 passed in 8.94s. Frontend lint/typecheck/build, security,
platform-admin, staging-config GREEN. No migration:
Alembic b0d2f4a6c8e1 / 105 tables. Frozen docs/ untouched.
Previous handoff-only CI 36279482610 was superseded/cancelled,
not evidence of a source failure.

Enhanced catalog entry property.gross_potential_rent is linked at
/dashboard/reporting/gross-potential-rent. Read-only preview
GET /api/reporting/gross-potential-rent/preview sets no-store,
and canonical server CSV/email delivery reuses shared
ReportActions and formula-safe CSV renderer.
Service app/services/gpr_report.py reuses verified
gpr_posting.month_bounds/_active_lease_for_month logic,
without invoking post_gpr or writing GL.
Per active live visible unit with positive CURRENT market
Unit.monthly_rent, the reporting-month overlap of ACTIVE lease
determines CURRENT contract scheduled amount, vacancy, and
loss/gain. Multiple overlapping active leases fail closed.
An old month is NOT a frozen historical rent snapshot.
Posted GPR JOURNAL_ENTRY source/unit/month transaction markers
are separate from these changing current-config estimates;
reversed original GPR markers and reversal IDs are distinguished.
No posted accounting *amount* or reconciled GL income claimed,
no merger of projected amounts with ledger postings.
ADMIN/MANAGER only; visible_budget_property verifies active user,
same-org, property ID, live manager assignment and
REPORTING.ALL/PROPERTIES.ALL/ACCOUNTING.GL_ACCOUNTS.
Additional LEASING and ACCOUNTING.JOURNAL_ENTRIES permission
required before lease and journal reads. REPORTING.ALL and
release.reporting.export rechecked on preview/export/email.
Foreign and unassigned property ID probes fail closed.
4 focused new regression tests: occupied/vacant amount,
old-month/current rent correction, original/reversal marker,
overlap and invalid input, organization/manager visibility,
no new GL entries, CSV formula escaping, preview no-store,
email and permission/export revocation. Existing 3 E2E browser
smoke tests are general, not dedicated interactive GPR tests.

NEXT ORIGINAL Section 38: Lease Expiration Detail,
then Lease Expiration Summary by Month, then Property
Directory. Current Lease.end_date and status are contract
data and do not prove actual move-out or renewal. Build
scoped read-only detail and aggregates from authorized
lease/unit/property records, no invented tenant status or
GL changes. Reuse REPORTING.ALL/LEASING, property
visibility and shared CSV/email. Include focused tests.

## Phase 3.7 Lease Expiration Detail and Summary — VERIFIED 2026-09-26

Product source 08fb55bb470e94e1422cd6b601a28794151c1f46;
summary-link/UI route correction d818dfbb5652c3f2d0735fa1b891a59c3be38ee2.
Final full CI 36280075299 SUCCESS: backend 489 passed,
3 deselected, 7024 warnings in 100.03s; browser E2E 3 passed
in 6.11s; frontend lint/typecheck/build, platform admin,
security, staging-config GREEN. Initial code run 36280041204
and superseded docs CI 36279978195 cancelled by newer pushes;
they are NOT full CI evidence. No migration, Alembic
b0d2f4a6c8e1 and 105 model tables. Frozen docs/ unchanged.

Both standard catalog keys property.lease_expiration_detail and
property.lease_expiration_summary have working customer links.
Detail /dashboard/reporting/lease-expirations, monthly summary
/dashboard/reporting/lease-expirations/summary opens directly in
summary mode. Shared selectable UI route displays date range,
optional property filter, scheduled end dates; generic server
CSV/email via ReportActions. Preview
GET /api/reporting/lease-expirations/preview sets no-store,
strictly allowlists report_key and excludes it from filters.
Service app/services/lease_expiration_report.py reuses only
actual Lease.end_date (ACTIVE or EXPIRED recorded statuses).
TERMINATED/CANCELLED/DRAFT omitted; do not interpret scheduled
end as verified notice, renewal or move-out. Summary groups exactly
the same authorized detail rows by scheduled-end month and
property, counts lease IDs and sums recorded monthly contract rent
(not earned revenue or cash receipts). No GL writes/migrations.
Only active ADMIN/MANAGER and live org-scoped, nondeleted property,
unit, tenant records. Managers only live assigned properties;
cross-org tenant linkage refused. REPORTING.ALL/LEASING/
PROPERTIES.ALL plus release.reporting.export enforced before
preview, export and email; invalid date/filter scope fails closed.
User/customer email names and property text CSV formula-escaped.
Four focused tests cover status inclusion/exclusion, monthly
sums, foreign/unassigned scope, manager/tenant role, invalid
parameters, revocation, no GL writes and CSV/email. Three
general authenticated browser smoke tests, not dedicated report
workflow E2E.

NEXT ORIGINAL SECTION 38: Property Directory, then Property Group
Directory, Property Performance, Rent Roll, Unit Directory,
Unit Inspection, Unit Vacancy Detail. Models currently expose
Property/Unit and PropertyAssignment; NO verified PropertyGroup
model found yet. Do not invent a group classification: inspect
existing schema before building grouping report; add explicitly
maintained group membership if original feature requires it.

## Phase 3.7 Property Directory — VERIFIED 2026-09-26

Source 992c949d2ae079f424a8f16bbb8fa131cadf1048,
full CI 36280429259 SUCCESS six jobs: 492 backend passed,
3 deselected, 7112 warnings in 79.68s; authenticated E2E
3 passed in 9.11s; frontend lint/typecheck/build, security,
platform-admin and staging-config SUCCESS. No migration:
b0d2f4a6c8e1 and 105 model tables; frozen docs/ unchanged.
Superseded handoff-only CI 36280378419 cancelled; not
a product failure.

Catalog standard property.directory links to
/dashboard/reporting/property-directory. New service
app/services/property_directory.py uses only recorded
active, undeleted property identity/type/address and count
of active, undeleted Unit records. No inferred occupancy,
collected rent, owner/tenant contact or GL movement.
Admin sees own-org active property records; manager sees
only live actively assigned properties. Role status, org,
REPORTING.ALL/PROPERTIES.ALL and release.reporting.export
checked for preview/export/email. Optional property ID and
PropertyType enum filters validated; foreign/unassigned
ID probes fail closed. GET
/api/reporting/property-directory/preview no-store.
Shared ReportActions uses server-rerendered CSV/email,
CSV formula escaping; three focused backend tests for
counts, active/inactive, org/manager scope, bad params,
role/menu/export revocation, no ledger writes and delivery.
Three E2E tests are existing generic smoke, not dedicated
directory UI tests.

Exact next original Phase 3.7 report Property Group
Directory. Critical dependency: original PROJECT_MASTER
Section 15 explicitly says "Named groups for filtering,
access, reporting"; parity item properties.groups is
scheduled Phase 3.5 and settings.property_groups scheduled.
No PropertyGroup/PropertyGroupMembership model found in
backend/app/models or property.py. Properties page still has
a disabled release.properties.groups compatibility slot;
feature definition specifies entitlement property_groups,
PROPERTIES.GROUPS menu permission and org config gate.
Do NOT invent membership based on property name/type.
Build explicitly authorized named-group CRUD and real
org/property membership then report from persisted groups.
Preserve Hybrid Capability Gating and manager assignment;
report must not leak hidden member properties and should
mark filtered membership counts clearly. Migration + guards
and tests required if new group tables are added.

## Phase 3.7 Property Group Directory — VERIFIED 2026-09-26

Source b246d698b2da335796f9aca58ca4d067fb939cc0,
frontend type correction 70900226383d4421193ca8f7c76da465369e01f9.
Final CI 36280886202 SUCCESS all six jobs: 496 backend
passed, 3 deselected; E2E 3 passed in 10.46s.
Migration c1e3f5a7b9d2 adds property_groups and
property_group_memberships; 107 SQLAlchemy tables. Original
property groups prerequisite now persisted as explicit org-scoped
named groups and memberships; no invented auto-grouping.
Only authorized ADMIN can edit, scoped MANAGER sees currently
assigned property memberships. Hybrid release.properties.groups,
commercial entitlement, PROPERTIES.GROUPS and SETTINGS safeguards
apply. Canonical report preview, server CSV/email, permission/export
checks, formula-escaped CSV and manager scope included. No frozen
docs/ changes. Earlier source runs superseded/cancelled.

## Phase 3.7 Property Performance — VERIFIED 2026-09-26

Source 5c3149c27398b2c321062263795149a594ff63ab.
GitHub CI 36283808654 SUCCESS all six jobs: backend
499 passed, 3 deselected, 7403 warnings in 109.00s;
E2E 3 passed in 7.31s; frontend lint/typecheck/build,
platform-admin, security, staging-config green.
No migration from group head c1e3f5a7b9d2, 107 tables.
Frozen docs/ not changed; planning parity status not advanced.

Enhanced Property & Unit catalog key property.performance
links to /dashboard/reporting/property-performance. A mandatory
property ID and calendar year scope recorded GL income and
expense entries, including original and reversal postings.
Totals are credit-minus-debit for income and debit-minus-credit
for expenses; posted net is income less expense. Propertyless
company-level GL entries, other property/organization entries,
and asset/liability/equity lines excluded. Archived GL accounts
remain included when actual posted activity exists.
Role and live assigned-property checks reuse the VERIFIED
visible_budget_property helper: only org active ADMIN/MANAGER,
REPORTING.ALL, PROPERTIES.ALL, ACCOUNTING.GL_ACCOUNTS.
Explicit ACCRUAL basis only, CASH refuses rather than inventing
cash flow; no ROI, NOI, occupancy, rent roll or GL postings inferred.
Preview GET /api/reporting/property-performance/preview no-store;
existing ReportPayload and ReportActions provide server CSV/email
with release.reporting.export and formula escaping.
Three focused tests cover 2026 journal/reversal sums, org and
manager isolation, CASH refusal and bad parameters, no GL writes,
catalog and no-store preview/CSV/email/revoked export.
Three existing generic E2E smoke tests, not dedicated
Property Performance UI tests.

NEXT original Section 38: Rent Roll report, then Unit Directory,
Unit Inspection and Unit Vacancy Detail. Current Unit.monthly_rent
represents CURRENT configured market rent and Lease.monthly_rent
is CURRENT recorded contract rent; Lease.status and dates are
not immutable historical occupancy. Build a clearly qualified
current-config rent roll based on active scoped units and live
eligible leases. Do not claim collected rent or retroactive
historical occupancy, synthesize tenant links, ignore overlapping
active leases or bypass LEASING/property access. Only recorded
contract status/date, not live collection. Include focused tests,
preview no-store, shared CSV/email and existing export gate.
No new migrations needed if reading current tables.

## Phase 3.7 Rent Roll — VERIFIED 2026-09-26

Implementation source 8636280f378db4eda2679fee75e699bae139222a;
frontend filter typing correction
47fddcdd761fcc434c8e8b60afca87d31800e4f0.
First source CI 36284142345 reported one TypeScript error:
union optional property_id cannot be assigned to Record<string,string>;
its backend/E2E were canceled after the correction. Final
CI 36284240929 SUCCESS all six jobs: backend 502 passed,
3 deselected, 7536 warnings in 99.29s; E2E 3 passed in 7.53s;
frontend lint/typecheck/production build, security, platform-admin
and staging-config SUCCESS. No migration, Alembic c1e3f5a7b9d2
and 107 model tables. Frozen docs/ unchanged.

Enhanced catalog property.rent_roll links to
/dashboard/reporting/rent-roll. GET
/api/reporting/rent-roll/preview sets no-store.
Only current, active/undeleted org-scoped properties and unit
records are reported. Recorded Unit.monthly_rent is current
configured market rent; current eligible ACTIVE Lease with
recorded start<=today<=end gives Lease.monthly_rent and
same-org active TENANT association. No eligible lease is labeled
"not verified vacancy", not a physical occupancy claim.
Overlapping eligible active leases and invalid cross-org
tenant links fail closed rather than selecting a contract
or fabricating vacancy. Ended or terminated leases excluded.
Staff ADMIN/MANAGER, live property assignments, REPORTING.ALL,
PROPERTIES.ALL, LEASING, release.reporting.export checked;
optional property filter forbids foreign/unassigned ID probing.
No historical rent, GL income, collected payments or bank
activity inferred; no GL edits or migrations.
ReportPayload, CSV formula escaping and shared ReportActions
CSV/email delivery reused. Three focused regression tests
cover current market/contract distinction, no-lease/ended/
inactive unit, foreign and manager scopes, duplicate leases,
invalid tenant link, no GL writes, permissions, export
revocation and no-store preview/CSV/email. E2E 3 are generic
browser smoke tests, not dedicated Rent Roll E2E.

NEXT original Section 38 Unit Directory. Use recorded
active/undeleted Unit rows (layout, current configured rent,
deposit, availability flag, listing flag) from scoped active
Property; do NOT infer physical occupancy from is_available
or add unrelated lease/GL reads. Reuse existing catalog,
ReportPayload, role/menu/export gates and CSV/email delivery.

## Phase 3.7 Unit Directory — VERIFIED 2026-09-26

Source c1f47e197a8934634b88c77d5a04f0c97609c3a7;
test-only wording correction a608b1b2e86f2378df825c53d864413c2139197a.
First CI 36284591238 backend 504 passed, 1 failed,
3 deselected: test incorrectly expected literal "vacancy"
in a correctly worded disclaimer. Frontend/security/admin passed;
staging and E2E skipped. Only the incorrect assertion changed.
Final CI 36284770912 SUCCESS all six jobs:
505 backend passed, 3 deselected, 7629 warnings in 105.81s;
E2E 3 passed in 9.15s; frontend lint/typecheck/build,
security, platform-admin, staging-config green.
No migration; head c1e3f5a7b9d2, 107 model tables.
No frozen docs/ changes.

Standard catalog property.unit_directory links to
/dashboard/reporting/unit-directory. GET
/api/reporting/unit-directory/preview no-store.
Service app/services/unit_directory.py reads actual active,
undeleted Unit rows of current active, undeleted Property.
Includes only configured layout, market rent, security/pet
deposits/rent and editable is_available/is_listed and
available_from inventory flags. Flags explicitly do NOT
establish physical vacancy, occupancy, tenant or payment.
ADMIN/MANAGER only; managers only live assigned properties;
REPORTING.ALL, PROPERTIES.ALL, PROPERTIES.UNITS and
release.reporting.export gate rechecked for preview/CSV/
email. Optional property filter rejects foreign/unassigned
IDs. Existing ReportPayload, server CSV/email and formula
escaping reused; no GL changes, source screenshots or
new unrelated entitlements. Three focused tests cover
inventory values, inactive/deleted and foreign inventory,
manager/tenant scope, permission/gate revocation, no GL
writes, server delivery and no-store. Three generic
E2E browser tests (not dedicated Unit Directory interaction).

NEXT: original Section 38 Unit Inspection report.
As of this source there is no UnitInspection or
recorded inspection result model; full mobile/offline/
photo/checklist inspections are separately scheduled
in Phase 5, not verified. Do NOT fabricate inspections
from Unit.is_available, WorkOrder, tenant notes or photos.
If needed for Phase 3.7 report, pull forward only a
minimal explicit authorized inspected-date/unit/condition
and finding-record prerequisite, add scoped model/migration
and tests, and clearly differentiate it from Phase 5
inspection workflow. Unit Vacancy Detail follows Unit
Inspection in the original Section 38 order.

## Phase 3.7 Unit Inspection — VERIFIED 2026-09-26

Product implementation deb6019ab889c03e8ce5a208da271cb16e16d2a5;
focused test-only correction
52369dd6ae3237fa4695d1407750c18a3847959e.
First CI 36285181154 backend 507 passed / 2 failed /
3 deselected: direct route test omitted FastAPI Query default
and foreign-org test expected a generic permission error
instead of scoped "Property not found". Corrected tests
without weakening access control. Full CI 36285989151
SUCCESS all six jobs: backend 509 passed, 3 deselected,
7736 warnings in 109.67s; authenticated browser E2E
3 passed in 9.30s. Frontend lint/typecheck/build,
platform-admin, security and staging green. Three E2E
tests are the generic smoke flow, NOT dedicated inspection UI tests.

Migration d2f4a6c8e0b1 adds one
unit_inspection_records table; 108 model tables. New
app/models/unit_inspection.py, service
app/services/unit_inspections.py, router
app/routers/unit_inspections.py and related schemas.
The report is STANDARD property.unit_inspection at
/dashboard/reporting/unit-inspections with no-store preview
GET /api/reporting/unit-inspections/preview and shared
CSV/email ReportActions. Records are explicitly staff-entered,
append-only date/condition/findings linked to a real visible,
active, undeleted unit/property; creation is audited.
No record does NOT imply an inspection passed. This is
NOT a Phase 5 mobile/offline/photo/checklist inspection.
No work order, inventory flag or tenant note is promoted
to a verified inspection; no GL mutations.
Admin/manager only; manager requires live assignment.
REPORTING.ALL, PROPERTIES.ALL, PROPERTIES.UNITS, and
release.reporting.export rechecked for preview, CSV and
email. Foreign/unassigned property/unit IDs fail closed.
Four focused tests validate explicit rows, empty report,
audit, no GL writes, org/manager isolation, role/permission
revocation, invalid dates and recorded conditions, CSV
formula escaping, preview/export/email and gate revocation.
Frozen docs/ unchanged and parity metadata not advanced.

NEXT Unit Vacancy Detail. Existing verified Rent Roll
already distinguishes CURRENT eligible ACTIVE lease
association from absence of a recorded eligible lease;
Unit Directory separately exposes editable available/listed
flags, which do not prove physical occupancy. Reuse
these verified scoped services rather than implement
another occupancy or GL model. Report must identify only
"no eligible current recorded lease" CANDIDATES and
explicitly say physical vacancy is not verified; do not
label units "vacant" purely from is_available or
past lease date. Preserve manager/property/LEASING/
PROPERTIES.UNITS permissions and CSV/email gates.
No migration required if reusing source records.

## Phase 3.7 Unit Vacancy Detail — VERIFIED 2026-09-26

Source e61115fd1d0a544c7cddbfd0d8e22df6054ee8da;
focused test-state correction
0567aa87b894baf41238b61838566b71bc885a9b.
Final CI 36286373738 SUCCESS all six jobs:
backend 512 passed, 3 deselected, 7856 warnings
in 107.31s; authenticated E2E 3 passed in 8.86s;
frontend lint/typecheck/production build, platform
admin, security and staging-config green. The original
source run 36286344811 was superseded/cancelled after
the test correction; not a verified product CI run.
No migration: Alembic d2f4a6c8e0b1, 108 model tables.
Frozen docs/ unchanged. Planning parity metadata not advanced.

Canonical STANDARD property.unit_vacancy_detail links to
/dashboard/reporting/unit-vacancy-detail; preview
GET /api/reporting/unit-vacancy-detail/preview no-store.
Service app/services/unit_vacancy_detail.py composes
VERIFIED scoped rent_roll and unit_directory builders:
only active in-scope units with NO ELIGIBLE CURRENT
RECORDED LEASE are shown, with explicitly editable
is_available, is_listed, available_from and current
configured market rent. The report NEVER certifies
physical vacancy, historical occupancy, collected rent
or return. A FALSE is_available flag can still appear
when no eligible lease exists; the distinction is
explicit. Rent roll's duplicate active lease and
foreign-tenant guards fail closed. No GL writes.
Role ADMIN/MANAGER, org live manager assignment and
REPORTING.ALL, PROPERTIES.ALL, PROPERTIES.UNITS,
LEASING are all rechecked through the reused builders.
release.reporting.export and per-report permissions
required on preview, server-rendered CSV and email.
ReportPayload + CSV formula escaping, shared ReportActions
and safe optional property filtering reused unchanged.
Three focused tests cover current/expired/terminated
lease distinction, editable flags, inactive units,
manager org scope, invalid params, duplicate active
leases, permission/export revocation, preview CSV/email,
no GL writes. Three generic browser E2E smoke tests,
NOT dedicated vacancy interactions.

NEXT original Section 38 Owner & Vendor reports:
Owner Directory, Owner Statement, Vendor Directory,
Vendor Ledger, Work Order. Owner Statement is already
VERIFIED and must not be repeated. Source User has
only first_name, last_name, email, phone; do not
invent owner mailing addresses or use encrypted
tax profile identifiers. PropertyOwner is real
org-scoped ownership/membership if associated
property information is needed; verify active role,
org and visible property before showing owner links.
Preserve PEOPLE.OWNERS role/menu permission and
customer privacy; do not expose other owners to
ordinary owner or tenant viewers. No GL modifications.

## Phase 3.7 Owner Directory — VERIFIED 2026-09-26

Implementation 22bc827577e960a1e4a66203bebe14b7638df58c;
test-only CSV formula and foreign owner self-scope correction
96d731902ac3b3126ab8d93f7d4881a551795609;
security role-boundary correction
05c8e4e73a9e4c93088ddf2773318179dfd0b592.
Final source CI 36287053275 SUCCESS all six jobs:
515 backend passed, 3 deselected, 7963 warnings
in 107.66s; 3 authenticated browser E2E passed
in 8.99s; frontend lint/typecheck/build, security,
platform admin, staging-config green.
Superseded earlier source runs 36286827190 and
36286839810 CANCELLED, not fully verified.
No migration: d2f4a6c8e0b1, 108 model tables;
frozen docs/ unchanged, planning parity not advanced.

STANDARD owner.directory links to
/dashboard/reporting/owner-directory. Canonical preview
GET /api/reporting/owner-directory/preview with no-store;
existing ReportPayload/server CSV/email/ReportActions,
formula escaping and release.reporting.export rechecks.
Service app/services/owner_directory.py lists only
current active undeleted same-org User.role OWNER
contacts: recorded name, email, phone, Owner ID.
No invented owner mailing addresses, ACH banking,
TIN or tax profile reads. Existing users.get_user
restricts managers to crew details; therefore THIS
report denies MANAGER, even with a PEOPLE.OWNERS
menu grant. Authorized ADMIN sees same-org owners;
OWNER self sees own contact ONLY, never other owners.
REPORTING.ALL and PEOPLE.OWNERS required; tenant,
vendor, inactive/deleted and foreign scope denied.
Three focused tests cover role privacy, cross-org
owner self-only, inactive/deleted, CSV injection,
no GL writes, export-gate/menu revocation, preview
and server CSV/email. General E2E smoke count is
not owner-directory-specific coverage.

NEXT Vendor Directory (Owner Statement already VERIFIED).
Vendor is currently User.role VENDOR; there is
NO separate Vendor model, and Bill.payee_name is
unlinked free text for some records. Do NOT invent
vendor entities from unlinked bills or treat VENDOR_CREW
as a vendor business. Existing User has first/last,
email and phone, not verified vendor mailing address.
Preserve user-management role boundaries: manager
currently cannot list vendor users via GET /users
(it returns crew only); do not use report permissions
to widen that rule. ADMIN can view own-org vendor
accounts; owner sees nonowner users on existing
user-management GET /users (check current route),
but do not expose unrelated vendor contacts to
unauthorized tenant/crew/vendor roles.
Do not expose vendor tax profiles or internal payer details.


## Phase 3.7 Vendor Directory — VERIFIED 2026-09-27

Source 840a10ef8d4ecb791b24cb2ef09952f09b2c5cc7;
scope regression fix 74fc8455d63d6dac52374ea74e3a8668aba58e71.
CI 36287404716 SUCCESS six jobs: 518 passed backend,
3 deselected; authenticated E2E 3 passed in 10.64s.
No migration; head d2f4a6c8e0b1 / 108 tables. Frozen docs unchanged.

STANDARD vendor.directory at /dashboard/reporting/vendor-directory:
recorded active undeleted same-org User.role VENDOR contacts only;
UserRole.VENDOR_CREW, cross-org and free-text Bill payees excluded.
Only ADMIN and OWNER match existing /users contact visibility;
MANAGER is denied (existing manager users API is crew-only).
REPORTING.ALL and PEOPLE.VENDORS, export release gate checked.
Canonical preview no-store, ReportPayload formula-escaped CSV
and server email. No banking/taxpayer or invented mailing data.
Regression tests include foreign vendor-actor denial.

## Phase 3.7 Vendor Ledger — VERIFIED 2026-09-27

Source fe0f0d44e129cb5dd21e7b6a0ea7d0b434e8fbed.
CI 36300269360 SUCCESS six jobs: 522 backend passed,
3 deselected, 8188 warnings in 91.93s; E2E 3 passed
in 10.58s. Frontend lint/typecheck/build, security,
platform-admin, staging-config green. These E2E are generic
authenticated smoke, not vendor-ledger-specific interactions.
No migration: d2f4a6c8e0b1; 108 model tables.
Frozen docs and planning parity left unchanged.

ENHANCED vendor.ledger at
/dashboard/reporting/vendor-ledger, preview
GET /api/reporting/vendor-ledger/preview (no-store).
Only ADMIN current active undeleted same-org with REPORTING.ALL,
PEOPLE.VENDORS, ACCOUNTING.PAYABLES can access. Financial
ledger does not widen OWNER or MANAGER contact/report access.
User.role VENDOR recipient linkage must be an explicit
Bill.payee_user_id; no guessed vendor from Bill.payee_name
or unrelated VENDOR_CREW/tax data. Only active undeleted
registered vendor users and active, unreversed, non-VOID,
undeleted bills are included. Cross-org user links excluded;
foreign vendor_id probes fail closed. Optional vendor_id,
date_from, date_to validated. CSV formula escaping and
server CSV/email recheck report permission plus
release.reporting.export. Five focused assertions across
four focused tests validate role/menu/org scope, metadata
amounts, invalid values, CSV/email, no GL writes, revocation.

IMPORTANT SEMANTIC LIMIT: this is a read-only RECORDED LINKED
BILL AP REGISTER with Bill.amount and Bill.amount_paid metadata,
and their difference. It is NOT the full historical vendor
GL cash/payment ledger. Reversed/void/archived bills, unlinked
payees and detached vendor accounts are excluded. No inference
of tax reportability, accounting postings, cash balances or
historical paid events. Do not misstate these limitations.

NEXT ORIGINAL Section 38 Owner & Vendor item: Work Order.
Reuse REAL WorkOrder / Property / Unit / assignment records
and existing work-order user-visibility semantics. WorkOrder
has tenant_id, description and entry_notes that can be sensitive:
avoid printing entry notes, photographs, private history,
tax/banking or tenant PII. Current reporting should show
recorded work order id, location, title, category, priority,
status and timestamps, with clearly recorded costs only.
Role-scope active org ADMIN/OWNER/MANAGER; manager must
be live-assigned. Enforce REPORTING.ALL and
MAINTENANCE.WORK_ORDERS plus export release gate on
preview/CSV/email; no leak via foreign property_id probe.
No migration expected if only existing WorkOrder rows.

## Phase 3.7 Work Order Report — VERIFIED 2026-09-27

Product source ecf5d652e0ec9ca2b0428934446e1073b8d6a629.
CI 36300632574 SUCCESS six jobs: backend 526 passed,
3 deselected, 8317 warnings in 107.50s; browser E2E
3 passed in 8.74s; frontend lint/typecheck/production
build, platform-admin, security, staging-config all green.
Generic E2E smoke, not dedicated work-order interactions.
No migration: d2f4a6c8e0b1 / 108 tables;
frozen docs and planning parity unchanged.

STANDARD maintenance.work_order links
/dashboard/reporting/work-orders. No-store preview
GET /api/reporting/work-orders/preview and existing server
ReportPayload/CSV/email, release.reporting.export check,
formula-escaped CSV. Current ADMIN/OWNER/MANAGER only
with REPORTING.ALL and MAINTENANCE.WORK_ORDERS.
Managers have active undeleted property assignments,
all roles org scope plus active undeleted Property/Unit.
Foreign/unassigned property-id probes fail closed.
Allowed filters property_id, created date range, current
status. Report uses REAL WorkOrder title/category/priority/
status, property/unit references and recorded timestamp/
total_cost fields ONLY. Excludes tenant ID, description,
entry notes, photo URLs and activity history. Recorded cost
is NOT a posted GL expense or bank payout; no GL writes,
no invented inspection or project activities.
Four focused regression tests cover privacy, org/manager
scope, invalid filters, permission/export revocation,
CSV formula escaping, preview, server CSV/email and
no GL mutations. No unrelated work-order workflow change.

NEXT ORIGINAL Section 38 Accounting reports:
Account Totals, then Balance Sheet, Bank Account Activity,
Bank Account Association, Cash Flow, Cash Flow 12 Month,
then other listed reports. Existing Chart of Accounts,
Trial Balance and per-account General Ledger VERIFIED;
do not rebuild. Account Totals must reflect real posted
org-scoped GL balances/period totals, including reversal
entries, with explicit ACCRUAL vs CASH handling. Do not
infer cash activity or historical snapshots from current
editable fields. Review original document and
reporting_basis/read-only GL services first; add tests
and preserve posted accounting integrity.

## Phase 3.7 Account Totals — VERIFIED 2026-09-27

Source 63c9272670d7eb2b4b509fbec70da681bbfd9767.
All-six-job CI 36300974942 SUCCESS: 529 backend passed,
3 deselected, 8424 warnings in 87.57s; E2E 3 passed
in 9.29s; frontend lint/typecheck/build, platform-admin,
security and staging-config green. E2E is generic
authenticated smoke, not dedicated account-totals UI test.
No migration: d2f4a6c8e0b1 / 108 model tables.
Frozen docs and parity unchanged.

STANDARD accounting.account_totals links
/dashboard/reporting/account-totals; preview
GET /api/reporting/account-totals/preview no-store.
ADMIN only, active/not deleted, REPORTING.ALL plus
ACCOUNTING.GL_ACCOUNTS, export gate on preview/server
CSV/email. Existing ReportPayload and CSV formula escaping.
Accrual-only REAL posted, org-scoped GLTransaction/GLEntry
summed by GLAccount, including reversal entries and
recorded activity on archived GL accounts. Optional
as_of cumulative cutoff; no cutoff means all recorded
transaction dates. Explicit include_zero for no-activity
accounts. Columns: posted debit, posted credit, signed
debit-minus-credit (not a normalized balance sheet).
CASH accounting basis refuses instead of fabricating
cash-basis GL balances. No GL writes or inferred cash.
Three focused tests cover sums/reversal/inactive accounts,
org isolation, role/menu denial, CASH refusal, invalid
params, formula escaping, no GL changes, CSV/email,
release revocation and no-store preview.

NEXT original Section 38: Balance Sheet. Existing
Trial Balance and Account Totals already provide
immutable posted GL totals. Balance Sheet should use
posted journal entries with account types ASSET,
LIABILITY, EQUITY, INCOME, EXPENSE, and explicitly
separate net unclosed income/expenses from equity;
do not infer balance from property market value or
current bill/receipt snapshots. Only ADMIN should
access full-org balance sheet without widening
owner-specific financial visibility. Respect
ACCRUAL/CASH basis and original report gates.
Test that assets = liabilities + equity + unclosed
earnings for balanced postings, including reversals,
and refuse inconsistent books rather than claim
a verified balance. Do NOT silently relabel this
as a GAAP audited financial statement.

## Phase 3.7 Balance Sheet — VERIFIED 2026-09-27

Product source 0d8f40db185126be26a67db32dbaa9126d02c782.
Full CI 36301335972 SUCCESS all six jobs: backend
532 passed, 3 deselected, 8547 warnings in 115.51s;
authenticated browser E2E 3 passed in 10.33s;
frontend lint/typecheck/production build, platform-admin,
security and staging-config SUCCESS. Generic E2E smoke,
not dedicated Balance Sheet interactions.
No migration: Alembic d2f4a6c8e0b1, 108 model tables.
Frozen docs and planning parity unchanged.

ENHANCED accounting.balance_sheet now links
/dashboard/reporting/balance-sheet. No-store preview
GET /api/reporting/balance-sheet/preview.
Reuses VERIFIED build_account_totals for ADMIN,
same-org active actor, REPORTING.ALL,
ACCOUNTING.GL_ACCOUNTS, posted accrual GL and
historical archived GL account balances.
Requires as_of. Assets debit minus credit; liabilities
and equity credit minus debit; explicitly shows
unclosed posted earnings = income minus expense.
Refuses to display if actual posted equation does not
reconcile, unknown account type or CASH basis.
Recorded reversal entries included; no guessed assets,
historical positions, bank values, income closing entries
or new GL postings; marked UNAUDITED.
Shared ReportPayload CSV/email and release.reporting.export.
Three new focused tests cover dated posted equation,
reversal/archived income, cross-org and roles,
unbalanced-book fail closed, CASH denial, CSV formula
escaping, no GL edits, menu/export revocation and
no-store preview/email delivery.

NEXT original Section 38 Banking/Accounting reports:
Bank Account Activity, then Bank Account Association,
Cash Flow, Cash Flow 12-Month. Existing BankAccount
maps bank accounts to GL cash account via gl_account_id.
BankAccount currently stores routing_number and
account_number as plaintext columns (!). DO NOT include
those fields in ANY new report, CSV, email or preview.
Bank feed inbox is not GL; bank reconciliation statement
balances and GL book balances are distinct. Design Bank
Account Activity as explicitly posted GL activity on the
selected org-scoped bank account's mapped GL cash account;
read immutable GLEntry/GLTransaction, include reversal,
and do not infer cleared/settled bank transactions.
Strict ADMIN/ACCOUNTING.BANK_ACCOUNTS and
ACCOUNTING.GL_ACCOUNTS checks. A bank ID must always
be scoped to actor's organization; reject foreign IDs.
Document ACCRUAL-only vs CASH-basis handling explicitly.
No migration if existing GL and bank mapping suffice.

## Phase 3.7 Bank Account Activity — VERIFIED 2026-09-27

Product source d90102a7cd1baa0ae71ff0dace48d70f6357c1dc.
Full source CI 36301725230 attempt 2 SUCCESS all six jobs;
backend 535 passed, 3 deselected, 8687 warnings in 61.26s;
E2E 3 passed in 9.16s; frontend lint/typecheck/build, platform-admin,
security and staging-config green. First attempt failed ONLY transient
E2E login navigation waiting for /dashboard load (2 passed, 1 failed);
one targeted retry succeeded, no product-code edit to auth.
No migration: d2f4a6c8e0b1, 108 model tables. Frozen docs unchanged.

STANDARD accounting.bank_activity links
/dashboard/reporting/bank-activity. No-store preview
GET /api/reporting/bank-activity/preview; shared ReportPayload/
CSV/email/release.reporting.export gate. ADMIN only, same-org
active/not deleted, REPORTING.ALL + ACCOUNTING.BANK_ACCOUNTS +
ACCOUNTING.GL_ACCOUNTS. Requires active in-scope bank_id.
Shows actual dated GLEntry/GLTransaction posted GL movement
on associated org ASSET GL account, opening debit-minus-credit,
running posted cash-book balance, reversal entries, date range.
CASH presentation refused because report is posted ACCRUAL GL.
Never uses bank-feed inbox, clearing/statement balances,
routing_number/account_number, foreign GL accounts or bank
settlement claims. Three focused tests cover date/opening/reversal,
foreign and role/menu/privacy, CSV formula escaping,
no GL edits, preview/email and export gate.

## Phase 3.7 Bank Account Association — VERIFIED 2026-09-27

Product 369f1e3f374397ca704219aa8995b5c5a0ffc159;
focused test isolation correction
73873fddb7fcf7aee7115d6de0d145fbb8d55ad9.
Initial source CI 36323157932 backend 537 passed /
1 failed / 3 deselected: test accidentally left GL permission revoked
before expecting a foreign-bank not-found error. No product
defect: restored test permission state. Final CI 36323294362
SUCCESS all six jobs: 538 backend passed, 3 deselected,
8766 warnings in 115.20s; browser E2E 3 passed in 9.95s;
frontend lint/typecheck/build, security, platform-admin,
staging-config green. The E2E is generic authenticated smoke,
not a dedicated association UI interaction.
No migration: d2f4a6c8e0b1 / 108 model tables.
Frozen docs/ source-of-truth files and parity status unchanged.

STANDARD accounting.bank_association links
/dashboard/reporting/bank-association. No-store preview
GET /api/reporting/bank-association/preview and shared
CSV/email ReportActions; rechecks REPORTING.ALL,
ACCOUNTING.BANK_ACCOUNTS, ACCOUNTING.GL_ACCOUNTS,
release.reporting.export. ADMIN-only, active same-org
with inactive/deleted actor denial, opt bank_id and include_inactive.
BankAccount -> GLAccount recorded mapping ONLY, not
property-to-bank mapping (no such relation on current Property)
and not statement/clearing/balances. Includes recorded
bank display name, type, status, mapped GL account name/number,
GL status and mapping review flag; not routing/account numbers,
ACH info, bank notes, foreign GL metadata. Inconsistent foreign
or missing GL mapping appears UNRESOLVED with no GL details;
non-ASSET mappings flagged for review. Archived bank records
visible only when include_inactive=true, and archived GL status
explicit. CSV formula escaping, invalid-filter and org ID probes,
role/menu revocation, release gate, server preview/CSV/email,
no GL writes covered in 3 focused tests. CASH/ACCRUAL accounting
basis is not applicable to a configuration-only mapping inventory.

NEXT original Section 38 Accounting report: Cash Flow, followed by
Cash Flow 12-Month. Use only real immutable org-scoped
posted GLEntry/GLTransaction and verified BankAccount
-> GLAccount cash mappings; do NOT infer historical external
bank settlements from bank feed, owner/bill snapshots or
routing/account fields. Read GLAccount.include_on_cash_flow
and accounting-basis semantics. Carefully distinguish
bank-mapped GL book cash movement from full classified
GAAP Statement of Cash Flows (the data currently lacks
independent operating/investing/financing classifications).
Bank-to-bank transfers may inflate gross posted inflows
and outflows while net book cash movement cancels.
Preserve role/menu/export checks and explicit limitations;
do not silently claim CASH-basis P&L, audited balances or
bank reconciliation. No migration expected if source GL
is enough. Include opening/ending posted book cash,
reversals, date filters and tests; identify how any unmapped
cash accounts affect completeness.

## Phase 3.7 Cash Flow — VERIFIED 2026-09-27

Source 0bce280bcd932b5ba1862689d14380ad620697fb;
test order correction 5305d8d4cd6c80f7ecb5cf893dbbfe100c3f1b0f.
First source CI 36323735841 FAILED only one test's
bank-record creation-order assumption (540 passed, 1 failed,
3 deselected). Bank rows legitimately sort by display name.
Test-only correction selected rows by bank ID; report code
not changed to satisfy the test. Final CI 36323986765
SUCCESS all six jobs: backend 541 passed, 3 deselected,
8964 warnings in 106.58s; authenticated E2E 3 passed
in 9.24s; frontend lint/typecheck/build, platform-admin,
security, staging-config green. E2E generic smoke; not
dedicated Cash Flow UI interactions.
No migration: Alembic d2f4a6c8e0b1 / 108 model tables.
Frozen docs and planning parity unchanged.

ENHANCED accounting.cash_flow at
/dashboard/reporting/cash-flow, preview
GET /api/reporting/cash-flow/preview no-store;
server ReportPayload, CSV formula escaping, shared
CSV/email ReportActions, release.reporting.export.
Authenticated ADMIN active/not-deleted same-org with
REPORTING.ALL, ACCOUNTING.BANK_ACCOUNTS and
ACCOUNTING.GL_ACCOUNTS. date_from/date_to mandatory,
validated inclusive date range; refused malformed/extra
query keys. Reuses actual same-org BankAccount -> GLAccount
mappings, only ASSET GL accounts marked
include_on_cash_flow=true. Includes archived bank/GL
records when their historical posted activity exists.
Actual org-scoped GLEntry/GLTransaction posted debit
and credit sums, opening before range, period movement,
closing and TOTAL; reversal journal entries included.
Cash-to-cash transfers inflate gross inflows/outflows
but cancel in net. No bank-feed inbox, statement
clearing, transaction settlement, or private bank
account/routing fields in preview, CSV or email.
Unmapped/excluded GL cash accounts are omitted and
explicitly disclosed. Broken foreign/non-ASSET mapping
fails closed. This is posted bank-mapped book-cash
movement, NOT classified GAAP/audited Cash Flows.
Accounting CASH vs ACCRUAL toggle does not magically
translate the immutable posted GL; report label
explicitly states posted book movement in both modes.
No GL writes. Three focused tests cover opening,
net transfer/reversal, missing/excluded mappings,
org/role/menu scope, input validation, basis behavior,
formula escaping, exported/email data and revocation.

NEXT original Section 38: Cash Flow 12-Month.
Reuse VERIFIED build_cash_flow for 12 full calendar
months ending in specified YYYY-MM. Derive per-month
period posted debit/credit, net, opening/closing
and grand totals. Preserve legacy month-end / year
rollover behavior, bank-mapped GL caveat, transfer
double-count gross only, role/menu/export restrictions.
One source implementation edge case: build_cash_flow
currently uses start.fromordinal(start.toordinal()-1)
for opening, which raises for date.min 0001-01-01;
fix safely and add an edge regression test when touching
this service. Do not alter accounting posting.
No database migration expected.

## Phase 3.7 Cash Flow 12-Month — VERIFIED 2026-09-27

Product source c1f97d1823c14a268d7f42263b379cb1f801263c;
pre-CI calendar-index correction d4b180fafd06f01b10b64c230184357f1a403881;
pre-CI fixed-width ancient-year label correction
0718264d01661140e592ad9008117b2c87740d1b.
Original uncorrected source CI 36324381414 and intermediate
36324402432 were cancelled/superseded; no false test results.
Final CI 36324425667 SUCCESS all six jobs: backend
545 passed, 3 deselected, 9224 warnings in 100.89s;
browser E2E 3 passed in 10.97s, frontend lint/typecheck/build,
security, platform admin, staging config GREEN. The E2E tests
are generic authenticated smoke, not dedicated 12-month UI.
No migration: Alembic d2f4a6c8e0b1 /108 model tables.
Frozen docs and planning parity unchanged.

ENHANCED accounting.cash_flow_12_month links
/dashboard/reporting/cash-flow-12-month. No-store preview
GET /api/reporting/cash-flow-12-month/preview;
server canonical ReportPayload, CSV formula escaping, shared
ReportActions CSV/email, release.reporting.export checked;
current user ADMIN, same-org, active/not deleted,
REPORTING.ALL + ACCOUNTING.BANK_ACCOUNTS +
ACCOUNTING.GL_ACCOUNTS repeatedly checked.
Requires strict ending_month YYYY-MM and uses 12 full
calendar months, including year rollover. Delegates each
month to verified build_cash_flow; explicitly posted
bank-mapped GL cash only, archived historical banks and
GL included, source asset/include_on_cash_flow filtering.
Shows opening, posted debit/inflow, posted credit/outflow,
net, ending per month; ending 12-month TOTAL and continuity
guard. Internal cash transfers inflate gross and cancel
net; unmapped and excluded cash GL records omitted;
no private bank account/routing numbers, bank feeds,
cleared settlement, fake classified GAAP statements
or GL mutations. Same posted-book data irrespective
CASH/ACCRUAL presentation toggle.
Fixed build_cash_flow earliest date 0001-01-01 opening
underflow by using < start filter rather than previous
ordinal; focused regression covers date boundary.
Three new 12-month regression tests validate rollover,
old-year carry/transfer/reversal, earliest calendar
edge, org/menu/role isolation, invalid month,
export gate, no-store preview, email, CSV, no GL writes.
One additional underlying cash-flow earliest-date test.

NEXT original Accounting report: Expense Distribution.
Source: org-scoped posted GLEntry / GLTransaction and
actual GLAccount.account_type=EXPENSE. Do not infer bills
or cash payouts from editable summary fields. Clearly
label posted accrual expense by account, reversal
effects, income/cash basis distinction, and categories
limited to genuine GL account metadata. Scope ADMIN,
REPORTING.ALL, ACCOUNTING.GL_ACCOUNTS, export gate;
date range filters, no GL posting, no invented
property allocations. Examine existing Account Totals
and reporting_basis as verified reference.
No migration anticipated. Add focused tests.

## Phase 3.7 Expense Distribution — VERIFIED 2026-09-27

Product source 67d8630f871e26226e8a280913742a4ae780d4c4.
Full CI 36324862669 SUCCESS all six jobs: backend
548 passed, 3 deselected, 9364 warnings in 93.26s;
browser E2E 3 passed in 9.80s; frontend, platform-admin,
security, staging-config all green. Generic authenticated E2E,
not dedicated expense report interactions. No migration;
Alembic d2f4a6c8e0b1 / 108 model tables.
Frozen docs/ and parity unchanged.
STANDARD accounting.expense_distribution links
/dashboard/reporting/expense-distribution, no-store preview
GET /api/reporting/expense-distribution/preview;
server ReportPayload/CSV/email reuse, release.reporting.export
gate, org ADMIN/REPORTING.ALL/ACCOUNTING.GL_ACCOUNTS.
Dated posted GL income classification EXPENSE by chart account,
net signed debits less credits, reversal and archived account
activity, optional include_zero, income/cash-basis excluded.
Share (%) meaningful when net positive; negative share permitted.
CASH reporting basis refuses rather than invent cash-basis expense.
Three focused tests verify real posted sums, date bounds,
reversals, negative and zero, cross-org/role/menu, CSV escaping,
no GL mutation, live authorization and email/export gate.

## Phase 3.7 Income Statement — VERIFIED 2026-09-27

Product commit c20ef1877bcde6b5c97da302e25e4767a7f07586.
CI run 36326806250 SUCCESS all six jobs:
backend 551 passed, 3 deselected, 9553 warnings in 118.92s;
authenticated browser E2E 3 passed in 5.97s;
frontend lint/typecheck/build, platform-admin, security,
staging-config all successful. E2E is generic browser smoke,
not dedicated income statement interactions.
No migration, Alembic d2f4a6c8e0b1 / 108 tables.
No frozen docs/ or parity edits.

ENHANCED accounting.income_statement links
/dashboard/reporting/income-statement.
GET /api/reporting/income-statement/preview is no-store;
existing backend ReportPayload / CSV email and export gate.
Current org ADMIN active/not deleted with REPORTING.ALL
plus ACCOUNTING.GL_ACCOUNTS required in router and builder.
Read-only dated posted GLEntry/GLTransaction grouped by
organization-owned GLAccount types INCOME and EXPENSE,
including archived accounts, credit returns/reversals and
negative signed balances. Revenue = posted credits minus
debits, expense = posted debits minus credits; net = income
minus expense. No invented closing adjustments, property
allocations, bank deposits, bill snapshots, GAAP audit status
or CASH-basis P&L; CASH view refuses. Required inclusive
date_from/date_to, optional include_zero, fail closed on
unknown/invalid filters. Three targeted regression tests
verify date/cross-org scope, account and reversal signs,
negative and zero, access/role/menu and CASH denial,
CSV formula escaping, no GL writes, preview/email/export
release revocation. Output labeled UNAUDITED.

NEXT original Section 38: Trust Account Balance, then Trust
Account Detail. Reuse real org-scoped BankAccount -> GLAccount
cash mappings, Account Totals / Bank Account Activity and
existing trust owner subledger/diagnostics where applicable.
Do not expose plaintext routing/account numbers stored on
BankAccount. Do not conflate posted GL BOOK cash with bank
statement balance, cleared reconciliation balance, tenant
deposit liability or owner subledger. Existing code currently
does not automatically prove three-way reconciliation.
A meaningful trust balance should reflect as-of posted
cash book by configured trust bank accounts, preferably
explicit account type and reconcile STATUS limitations.
Detect invalid/foreign GL mappings and duplicate mapping
double counting; refuse rather than fabricate trust funds.
Admin-only + REPORTING.ALL/BANK_ACCOUNTS/GL_ACCOUNTS,
release.reporting.export, no-store preview, CSV/email.
Document as-of and archived historical postings, future
date and zero balance choices. Tests for org and bank
probes, permissions, historical reversal, no PII, no
GL writes; no migration if verified source data suffices.

## Phase 3.7 Trust Account Balance — VERIFIED 2026-09-27

Product source 6c8ced27805a63e0ad715fac8eb46621c3c58c5a;
test-only assertion correction 9bd8e948d68dad97dd409ca11a7e0f95d3bf0443.
Initial CI 36327229773 FAILED one test: it tried to create
two bank records mapping the same org GL, which the database
rightly rejects under the pre-existing UNIQUE constraint.
Initial backend 553 passed / 1 failed / 3 deselected;
no report-code defect or schema change. The test now
asserts that existing SQL uniqueness and rolls back
before testing foreign-org mapping. Final full
CI 36327401270 SUCCESS all six jobs: backend 554 passed,
3 deselected, 9718 warnings in 115.00s; browser E2E
3 passed in 9.57s; frontend lint/typecheck/production build,
security, platform-admin and staging-config all GREEN.
E2E generic smoke, not dedicated trust report browser interaction.
No migration: Alembic d2f4a6c8e0b1 /108 model tables.
Frozen docs/ and parity status/counts unchanged.

ENHANCED accounting.trust_account_balance links
/dashboard/reporting/trust-account-balance. No-store preview
GET /api/reporting/trust-account-balance/preview;
shared backend ReportPayload, CSV/email ReportActions,
release.reporting.export. Requires org-active ADMIN
REPORTING.ALL, ACCOUNTING.BANK_ACCOUNTS and
ACCOUNTING.GL_ACCOUNTS; backend scope rechecked.
as_of required, optional bank_id. All org bank mappings,
including archived historical records, must point
to unique same-org ASSET GL accounts. Unknown/foreign
bank ID, foreign/nonasset GL or duplicate mapping
fails closed. Reuses verified cash_flow._account_totals
for posted GLEntry/GLTransaction through as_of.
Rows show bank ID, display name/type, archive status,
GL number/status and posted debit-minus-credit
book balance plus total; negative balances possible.
No bank account/routing, ACH, bank feed, bank
statement, cleared reconciliation, owner/tenant
liability, property inferred allocation or GL writes.
Title explicitly says unaudited book balances,
NOT a three-way reconciliation. Three new focused tests
cover date/archived/reversal/zero, duplicate DB
constraint, mapping errors, foreign/roles/menu, no
PII, formula escaping, preview/email/CSV and export
gate revocation. No change to verified Bank Activity.

NEXT Section 38 Trust Account Detail. Implement
entry-level dated book activity for selected
bank-mapped same-org ASSET trust GL; include opening
and running balance, real posted transaction IDs
and recorded owner/property tags only after same-org
verification. Unverified foreign owner/property tags
must not disclose foreign IDs/names; mark unresolved.
Do not infer bank settlement, reconciled statement
balance or owner funds from a GL entry tag.
Reuse trust balance mapping/permissions and verified
cash-flow opening, no sensitive routing/account fields.
Strict as-of/period validation, admin/report/export
gate, no-store preview, existing CSV/email actions.
Regression tests for allocation, archived historical
activity, org isolation, date/reversal, no GL writes.
No migration anticipated.

## Phase 3.7 Trust Account Detail — VERIFIED 2026-09-27

Source 28a697be8317f2754262881f0a3ce6efa4693693;
CI 36327838434 SUCCESS six jobs: backend 557 passed,
3 deselected, 9870 warnings in 81.80s; authenticated
E2E 3 passed in 9.03s; frontend lint/typecheck/build,
platform-admin, security, staging-config all passed.
E2E generic smoke, not dedicated trust detail UI test.
No migration: Alembic d2f4a6c8e0b1 / 108 tables.
Frozen docs/ and parity status/counts unchanged.

ENHANCED accounting.trust_account_detail links
/dashboard/reporting/trust-account-detail, no-store preview
GET /api/reporting/trust-account-detail/preview, shared
ReportPayload/CSV/email and export gate. Requires current
org ADMIN REPORTING.ALL, ACCOUNTING.BANK_ACCOUNTS,
ACCOUNTING.GL_ACCOUNTS; verified trust-account-balance
builder reused for same-org bank-to-ASSET GL mapping,
duplicate mapping guard, archived history and scope.
bank_id, date_from, date_to required. Trust cash GL
entries are posted GLEntry/GLTransaction only, with
opening and running as-of book balance through dates,
real recorded references and reversal entries.
Property/owner tags displayed as IDs only when matched
to same-organization existing Property and OWNER User;
foreign/corrupt IDs withheld, flagged UNVERIFIED.
A recorded GL tag is NOT proof of ownership/allocation,
nor a cleared bank transaction, bank statement,
liability statement or reconciled three-way position.
No bank routing/account numbers or GL writes.
Three new focused regression tests check historical/
archive/foreign tags, period/opening/reversal, org
isolation and roles/menu, foreign GL/bank probes, no PII,
CSV formula escaping, email, preview/no-store, export gate.

NEXT Section 38 Transaction report Aged Payables, then
Aged Receivables. Existing Bill holds mutable
amount_paid and status, payable gl_transaction_id,
due_date (optional), bill_date, status/is_reversed.
No historical as-of unpaid balances can be reconstructed
from live Bill.amount_paid alone; do not label current
recorded outstanding as historic. Aged Payables should
show current recorded open bill liabilities by due date
relative to an explicit reference date and separate
missing/future dates, with real recorded amounts and
safeguards against void/reversed/deleted bills or
unposted drafts. Verify bill workflow/GL pointer and
permissions before coding; reuse existing vendor ledger
and canonical report delivery. Do not alter GL or
infer paid checks/payment dates from mutable summaries.
No migration anticipated. Include org/menu/role, age
boundaries, CSV escape and gating tests.

### Phase 3.7 Aged Payables — VERIFIED 2026-09-27

Source 2558a0b11ab73463071de83c83e6d80aa94ecba2;
test-only 31–60-day assertion correction
895857091f918293761e39d6cb9fad12655fb5e0.
Source CI 36328376671 SUCCESS all six jobs:
backend 560 passed, 3 deselected, 10156 warnings in 119.72s;
browser E2E 3 passed in 8.74s; frontend, security,
platform-admin and staging-config GREEN.
No migration, Alembic d2f4a6c8e0b1 / 108 tables.
Frozen docs and parity not touched. Standard report
transaction.aged_payables at /dashboard/reporting/aged-payables
with server /api/reporting/aged-payables/preview and existing
CSV/email renderer. Current recorded unpaid posted Bill metadata
only; due-date 1–30/31–60/61–90/91+ buckets plus future,
due-today and missing dates; no historical snapshot.
Excludes void/reversed/deleted/unposted bills and fails
on bad status/amounts/foreign payable GL, enforces ADMIN,
REPORTING.ALL, ACCOUNTING.PAYABLES, ACCRUAL and
release.reporting.export. No GL writes or private bank details.
Three focused tests cover arithmetic, org/role, probes,
CSV escaping, preview/email/revocation. Earlier superseded
CI runs 36328190941 and 36328319776 were CANCELLED, not
proof of a product regression.

## Phase 3.7 Aged Receivables — VERIFIED 2026-09-27

Source 7af730729cd126b61331caf0b170b7e290eee0c9;
pre-CI preview summary-count correction
d1e2b0501602c33d61a9c901791286eef6a771cd;
test-only 1–30-day second-property bucket correction
545894bbe5f6acbef78a5b37ee58c707f55f5a81.
Initial source CI 36329370057 FAILED only a focused
test expectation: it omitted a legitimate $250
second-property invoice from 1–30 bucket. Backend
562 passed / 1 failed / 3 deselected. Product
logic left unchanged; corrected expected $400.
Final CI 36329631501 SUCCESS all six jobs:
backend 563 passed, 3 deselected, 10449 warnings in 82.71s;
E2E 3 passed in 8.37s, frontend lint/typecheck/build,
platform-admin, security and staging-config GREEN.
Browser E2E is generic authenticated smoke, not dedicated
receivables UI interaction. No migration; Alembic
d2f4a6c8e0b1 / 108 model tables. Frozen docs/parity unchanged.

STANDARD transaction.aged_receivables links
/dashboard/reporting/aged-receivables. Server
GET /api/reporting/aged-receivables/preview returns
no-store; shared ReportPayload and CSV/email gated by
release.reporting.export. Builder requires current active
org ADMIN or assigned MANAGER, REPORTING.ALL and LEASING.
Only active same-org tenant/units/properties, valid manager
property assignments; tenant_id/property_id probes fail
closed. Invoice status VOID excluded, fully paid excluded;
bad paid/rent/late-fee metadata refuses. Uses actual
RentInvoice due_date and current mutable amount_paid,
with separate 1–30/31–60/61–90/91+ age, future and
due-today sums. No historic "as-of" inference. No posted
GL AR assertion and no standalone Charge balances;
those might overlap invoice late fees and are kept
in separately verified Unpaid Charges reporting. No
GL/payment writes. Focused regressions cover boundaries,
partial/paid, org/assignment/role, invalid parameter and
corrupt metadata, CSV formula escaping, preview/email,
release and permission revocation.

NEXT original Transaction report: Bill Detail, followed
by Charge Detail. Inspect pre-existing verified Bill
detail modal, BillLine, GL posting and vendor ledger.
Implement scoped posted Bill header + recorded line
breakdown (do not pretend payment history or infer
foreign-account/property data). Reuse canonical report
catalog, server ReportPayload/CSV/email, strict access
and no-store preview, focused tests and full six-job CI.
Do NOT write GL or reconstruct historic payment snapshots.

## Phase 3.7 Bill Detail — VERIFIED 2026-09-27

Source bed121f5796aedd3c6985f5bda972e8dded32d45.
CI 36330083012 SUCCESS all six jobs: backend 566 passed,
3 deselected, 10632 warnings in 121.02s; browser
E2E 3 passed in 9.06s; frontend lint/typecheck/build,
platform-admin, security and staging-config green.
Browser E2E is the existing authenticated smoke, not
Bill Detail screen-specific automation. No migration:
Alembic d2f4a6c8e0b1 /108 model tables.
Frozen docs/ and planning parity unchanged.

STANDARD transaction.bill_detail links
/dashboard/reporting/bill-detail, no-store preview GET
/api/reporting/bill-detail/preview. Existing server
ReportPayload/CSV/email reuse + release.reporting.export
gate. ADMIN current active same-org user must have
REPORTING.ALL, ACCOUNTING.PAYABLES, ACCOUNTING.GL_ACCOUNTS.
Bill ID and inclusive bill_date filter optional; unknown,
foreign and non-posted bill IDs fail closed; at most 5000.
Source posted Bill linked to same-org original BILL
GLTransaction, excluding reversed GL/bill, void,
inactive and deleted. Same-org LIABILITY payable
GL and each BillLine same-org GL account checked,
line amounts positive and sum equals parent Bill.amount.
One BILL header displays current mutable status/amount/
paid/unpaid and separate LINE rows show recorded GL
account, line description/amount without repeating
bill total on every line. No owner/property identifiers,
private bank info or invented payment dates/checks,
no historic payable reconstruction and no GL writes.
3 focused regression tests: verified line split,
invalid GL/amount/foreign bill, roles/menu,
CSV formula escape, preview/email and export gate.
No further Bill Detail changes needed absent new evidence.

NEXT original Transaction report: Charge Detail,
then Check Register. Reuse verified Charge, tenant
unpaid charge and tenant ledger models/scoping.
Include PAID and outstanding standalone Charge records,
but never combine RentInvoice with Charge as its late fee
may already be in invoice. Charge.amount_paid and
is_paid are mutable current recorded metadata, not
GL-settled historic payments. In particular, Charge
has NO documented posted GLTransaction pointer, so
cannot claim GL-posted AR. Respect current access,
same-org tenant/properties, active assignment,
unallocated admin-only records and same-org GL code.
Use shared report delivery, no-store preview,
formula escape, regression tests and six-job CI;
do NOT rebuild existing Unpaid Charges report.

## Phase 3.7 Charge Detail — VERIFIED 2026-09-27

Source cc0d81971de51bf6b7c0b3cb3d0963b085514e8b.
CI 36330600066 SUCCESS all six jobs: backend 569 passed,
3 deselected, 10772 warnings in 97.78s; browser E2E
3 passed in 9.19s; frontend lint/typecheck/build,
platform-admin, security and staging-config green.
E2E only existing generic smoke, not dedicated Charge
Detail UI flow. Alembic d2f4a6c8e0b1/108 tables;
no migration, frozen docs/ and parity unchanged.
Previous Bill Detail handoff-only run 36330510399 may
have been superseded by this source push; do not claim
green without its own results.

STANDARD transaction.charge_detail at
/dashboard/reporting/charge-detail, authenticated no-store
GET /api/reporting/charge-detail/preview, shared server
ReportPayload/CSV/email with release.reporting.export gate.
Organization ADMIN or assigned MANAGER, active/current,
REPORTING.ALL, LEASING, ACCOUNTING.CHARGES,
ACCOUNTING.GL_ACCOUNTS. Filters charge_id, tenant_id,
property_id, charge_date inclusive range; max 5000
rows and foreign/unauthorized reference fail-closed.
Uses standalone Charge, User(TENANT), Property,
PropertyAssignment, Unit and same-org INCOME GLAccount.
Propertyless charges admin only; inactive/deleted and
foreign records excluded. Full paid, unpaid and recorded
overpay/credit included with warning when is_paid flag
disagrees with computed current balance; no made-up
credit settlement. RentInvoice intentionally excluded
as may double-count late fees. No GL posted AR assertion,
no historic balance or payment inference and no GL writes.
Three focused tests cover full/partial/credit arithmetic,
unallocated/assigned/foreign/invalid GL scoping, roles,
CSV escape, preview/email, revocation and export gating.

NEXT: original Transaction Check Register followed by
Check Register Detail. Reuse existing Check/
CheckBillAllocation, Check issue/void, BankAccount
and GLTransaction. Only same-org original CHECK GL
with correct void reversal state; do NOT expose
BankAccount.account_number or routing_number,
do not pretend issued checks have cleared bank,
and do not repeat check total on child allocations.
Preserve permissions and release gate; no writes.


## Phase 3.7 Check Register and Check Register Detail — VERIFIED 2026-09-27

Check Register source 1597120b55d45a37d17bc1baddf4c663abaec4b2,
CI 36331055801 SUCCESS all six jobs, backend 572 passed,
3 deselected, 10902 warnings in 122.35s; E2E 3 passed in 8.46s.
No migration, head d2f4a6c8e0b1 /108 model tables.

Check Register Detail source 9a1dd5dc941bb4a1043b7c367c072f3d4a54d61e,
authorization/catalog/delivery registration fix
0494f6a14bc8ee835837d87c5832995609b52c8f.
Initial run 36331816602 FAILED three new focused tests because
the initial tree omitted three modified existing registration files;
backend 572 passed, 3 failed, 3 deselected, 11004 warnings.
Corrective commit includes reporting router, catalog and dispatcher.
Final source CI 36332054459 SUCCESS six jobs; backend 575 passed,
3 deselected, 11004 warnings in 93.50s; E2E 3 passed in
10.62s, frontend/platform-admin/security/staging all green.
E2E remains the generic authenticated browser smoke, not
dedicated interaction coverage. No schema change, Alembic
d2f4a6c8e0b1/108 tables, frozen docs/parity unchanged.

STANDARD transaction.check_register is at
/dashboard/reporting/check-register; GET
/api/reporting/check-register/preview; existing server CSV/email
with export gate. Only active org ADMIN, REPORTING.ALL,
ACCOUNTING.BANK_ACCOUNTS + ACCOUNTING.PAYABLES. Validates
same-org BankAccount -> ASSET GL and original CHECK GLTransaction,
verified status and VOID reversal marker, capped filters, no-store;
exports bank display name only (never routing/account number).
An ISSUED check is NOT a cleared check; no bank settlement inference.

STANDARD transaction.check_register_detail is at
/dashboard/reporting/check-register-detail; GET
/api/reporting/check-register-detail/preview; existing
ReportPayload/CSV/email, release.reporting.export and no-store.
Reuses verified check-register filters/issue/void/authorization
and excludes foreign bills/invalid allocations. CHECK row has one
nominal total, ALLOCATION rows show bill ID/number and their
recorded amounts without repeating nominal total. Checks
allocation sum agrees with nominal check amount, refuses
negative/overprecision and cross-org bill ID. No GL writes,
bank secrets or historic bill payment reconstruction.
Three focused regression tests cover sums/invalid/foreign
allocation, role/filter protections, CSV formula escaping,
preview/email and live gate/permission revocation. No new
schema or parallel reporting implementation.

NEXT original Transaction report Deposit Register. Inspect
existing Deposit/DepositLine/Receipt/deposit_posting.
Deposits group existing posted receipts; deposits DO NOT post
new GL transactions or prove external bank settlement.
Deposit.bank_gl_account_id points to a GL account, not directly
to a BankAccount. Do not accidentally claim bank reconciliation,
double count posted receipts or expose routing/account numbers.
Validate same-org GL and included receipt/line org scope and
recorded totals; historical reversal/archived statuses must
be explicit. No mutation, report/admin/export gates, no-store
preview, CSV/email, focused tests. Only after six-job CI green,
continue Expense Register and Income Register in plan order.

## Phase 3.7 Deposit Register — VERIFIED 2026-09-27

Product commit bdf317cc8e2912061b1544229303aef12a1d3d34.
Full CI 36332538763 SUCCESS all six jobs: backend 578 passed,
3 deselected, 11124 warnings in 124.44s; authenticated browser E2E
3 passed in 8.76s; frontend lint/typecheck/build, security,
platform-admin and staging-config all passed.
No migration; Alembic d2f4a6c8e0b1 / 108 model tables.
Frozen docs/ and parity unchanged; generic E2E smoke only.

STANDARD transaction.deposit_register at
/dashboard/reporting/deposit-register with authenticated
GET /api/reporting/deposit-register/preview (no-store), shared
ReportPayload/CSV/email and release.reporting.export gate.
Requires active org ADMIN, REPORTING.ALL, ACCOUNTING.DEPOSITS,
ACCOUNTING.GL_ACCOUNTS. Optional deposit_id, bank_gl_account_id
(the cash GL, NOT physical bank ID), date range; 5000 row cap.
Verifies org ownership/ASSET cash GL, DepositLine organization,
unique same-org original posted Receipt and RECEIPT GLTransaction,
receipt reversals, positive amounts and sum against recorded
Deposit.total. Output only recorded deposit grouping, date,
number, cash GL display label, count, flagged reversed receipts
and nominal amount; never new GL cash, cleared banking,
reconciliation or routing/account numbers. No GL writes.
Three focused tests cover reversed receipt counts, org/amount/
GL/line probes, formula-escaped CSV, preview/email and gate/
role revocation. Existing deposit_posting and receipt_posting
untouched. Do not repeat.

NEXT Expense Register then Income Register in original Section 38.
Inspect posted accrual GLEntry/GLTransaction and GLAccount
EXPENSE/INCOME. PropertyExpense metadata is not a verified
posted GL source. Avoid presenting bills/bank cash as posted
expense accrual, double counting journal lines or inventing
cash-basis classifications. Reuse expense_distribution and
reporting_basis, admin org and GL permissions, no-store,
canonical ReportPayload/CSV/email, export gate and tests.

## Phase 3.7 Income Register — VERIFIED 2026-09-27

Source 3875ef5af74097f93643d6925eb8b14dfd6ac147.
Full GitHub CI 36335844931 SUCCESS all six jobs:
backend 584 passed, 3 deselected, 11380 warnings in 95.99s;
authenticated browser E2E 3 passed in 9.44s; frontend
lint/typecheck/build, platform admin, security and staging-config
all passed. Browser suite is generic authenticated smoke, not
dedicated Income Register page E2E. No migration; Alembic
d2f4a6c8e0b1 / 108 expected tables. Frozen docs and planning
parity unchanged.

STANDARD transaction.income_register links
/dashboard/reporting/income-register; authenticated no-store
GET /api/reporting/income-register/preview. Existing
ReportPayload, shared CSV/email ReportActions and
release.reporting.export gating reused. Only active same-org
ADMIN with REPORTING.ALL and ACCOUNTING.GL_ACCOUNTS.
ACCRUAL basis required; CASH basis refused rather than invent
cash-flow income. Actual dated posted GLTransaction/GLEntry
joined to same-org INCOME GLAccount, including archived
accounts, income credits, debit returns and reversal lines.
Signed net income = credits less debits. Strict date range,
optional account_id with org/type check; 5000 entry cap,
malformed/extra filters fail closed. Rows include real
transaction and entry IDs, recorded reference and description;
no receipt/bank clearing, invoice status or historic cash
claims; no GL writes. Three focused tests cover signed entries,
returns/archived history and org isolation, permission/release
revocation, CSV escaping, preview/email, invalid filters and
basis refusal.

NEXT original Section 38: Journal Entry Register. Inspect
existing /api/accounting/journal-entries and gl_posting,
GLTransaction.transaction_type JOURNAL_ENTRY and its
REVERSAL semantics. Original manual JE records may be
marked is_reversed=True while their reversal transaction
has type REVERSAL and reversal_of_id. Do not silently omit
historically posted originals or count reversals from
unrelated source types. Show recorded manual/recurring
journal metadata and true reversal markers, verify
balanced posted GLEntry lines, org-owned GL accounts,
date/role scope and no GL mutations. No new schema expected.
Preserve canonical report delivery, export gate, no-store
preview, formula escaping, focused tests and full six-job CI.

## Phase 3.7 Journal Entry Register — VERIFIED 2026-09-27

Source commit 329a85e1683f4392568f8d746404bec689c9b788.
GitHub Actions 36336312154 SUCCESS all six jobs:
backend 587 passed, 3 deselected, 11529 warnings in 126.65s;
authenticated browser E2E 3 passed in 10.07s; frontend
lint/typecheck/build, platform-admin, security and staging-config
passed. E2E generic smoke only, not dedicated Journal Register UI.
No migration; Alembic d2f4a6c8e0b1, 108 model tables.
Frozen docs and planning parity unchanged.

STANDARD transaction.journal_entry_register at
/dashboard/reporting/journal-entry-register, no-store preview
GET /api/reporting/journal-entry-register/preview; canonical
ReportPayload, shared CSV/email and release.reporting.export.
Active same-org ADMIN with REPORTING.ALL,
ACCOUNTING.JOURNAL_ENTRIES and ACCOUNTING.GL_ACCOUNTS.
Only GLTransaction type JOURNAL_ENTRY, plus REVERSAL whose
reversal_of_id points to same-org original JOURNAL_ENTRY.
Original journal marked is_reversed stays visible, and linked
REVERSAL lines show original ID and reversal status. Other GL
source types and unrelated reversals excluded. Validates
same-org GLEntry/GLAccount, positive single-sided debit/credit,
per-transaction balanced total. Date interval required;
optional transaction_id and include_reversals, 5000 txn/line
bounds, fail-closed on invalid/foreign references.
Posted debit/credit amounts unchanged by CASH/ACCRUAL
presentation setting, no bank clearing/GL mutation.
Three focused tests validate originals and linked reversals,
nonjournal exclusion, signed line arithmetic, archived GL,
org/role/menu, foreign account tampering, invalid filters,
CSV formula escaping, preview/email and live export gate.

Original Section 38 reports and customer-side prerequisites
are now verified except that actual external 1099 sandbox
acceptance, production filing, IRS receipt/corrections and
recipient copies remain provider/credential dependent.
Do not claim regulatory/operational 1099 filing complete;
vendor/report preparation features are not the same as
externally acknowledged 1099 forms.

NEXT original master Phase 4 starts with Full Vendor entity.
Current app has UserRole.VENDOR contact records but Bill.payee_name
remains free text; no durable Vendor model. Preserve verified
vendor directory/ledger and tax profiles; do not treat vendor
contact users as a fully implemented vendor company.
Inspect User, Bill, WorkOrder, access architecture and manual
Alembic migration patterns. Start bounded org-scoped Vendor
entity (company, contacts/address/trade, operational state)
with focused isolation, access and migration tests, then
continue insurance expiry and the planned real Vendor picker.
Do not auto-link historical free-text Bill payees by name or
migrate plaintext tax IDs. User only authorized narrow 1099
frozen-doc amendments; all other docs/ remain frozen.

## Phase 4 Vendor companies — VERIFIED 2026-09-27

Source 6e1d0eb730a71d913021b590667123ee047c4858.
GitHub CI 36336927654 SUCCESS six jobs: backend
590 passed, 3 deselected, 11598 warnings in 114.79s;
authenticated E2E 3 passed in 9.67s; frontend
lint/typecheck/build, security, platform-admin and staging
passed. Generic E2E only, no dedicated Vendor page browser E2E.
Manual Alembic e3f5a7b9c1d2 adds vendors table;
109 expected model tables; PostgreSQL/bootstrap/legacy
schema tests passed. Frozen docs/ and parity unchanged.

New app/models/vendor.py is a real organization-owned
vendor COMPANY distinct from UserRole.VENDOR portal/contact.
Optional contact_user_id must point to active same-org
role VENDOR user. Company name, trade, business email,
phone and address stored; NO tax ID fields.
Backend GET/POST/PATCH/DELETE/restore
/api/vendors, org role/menu PEOPLE.VENDORS.
Active same-org ADMIN may create/change/deactivate/
restore, OWNER may read/list, other customer roles
denied. Inactive/deleted actor denied, foreign IDs
404, live vendor-contact link validated fail closed.
Soft deactivation, list search/inactive filter, append-only
change audit, no-store reads, 1000-row bound. Frontend
/dashboard/vendors is already linked by verified sidebar
PEOPLE.VENDORS menu config; create/edit/contact link,
search/list/soft deactivate/restore.
No automatic Bill.payee_name mapping, no WorkOrder
assignment changes, no tax profile/1099 mapping;
verified vendor directory and ledger unchanged.
Three focused tests prove same-org CRUD, audit,
role/menu/contact/probe checks, archived lifecycle
and validation, no bill mutation. No other product
feature was represented as completed.

NEXT original Phase 4: Vendor insurance with recorded
coverage, policy number, carrier and expiration.
Inspect existing PropertyInsurance (different scope):
do NOT create expenses or GL entries from vendor
insurance premium metadata. Use org-owned Vendor model,
admin PEOPLE.VENDORS, verified record isolation and
authenticated document handling. Then vendor list
insurance-expiry filters, planned bill/work-order real
Vendor pickers, owner Vendor 1099 payer flag in dependency
order. Do not reuse general attachments for W-9s or
claim tax profile automatically linked to vendor
company; existing tax profiles still target UserRole.VENDOR.

## Phase 4 Vendor directory filters — VERIFIED 2026-09-27

Backend/service/tests commit b40d94b3861809d4cfd5bb563a21bd6a4e524476;
customer vendors page UI commit 0d32310911be49c9133ba002d19fdfdb9fce7e9a;
date.max overflow fix in existing vendor_insurance._status
87ed9dd1396686065c9596622173297628b2ace2.
Final six-job GitHub Actions run 36338819609 SUCCESS:
backend 596 passed, 3 deselected, 11742 warnings in 71.83s;
authenticated E2E 3 passed in 8.91s; frontend lint/typecheck/
build, security, platform-admin, staging-config all green.
E2E remains generic authenticated smoke, not dedicated vendor filter
browser interactions. Earlier superseded runs were CANCELLED, not
passed. No migration in the FILTER batch; existing vendor-insurance migration
head a9b1c3d5e7f0 / 110 tables unchanged.
Frozen docs/ and parity not edited.

Org-owned Vendor company list GET /api/vendors now supports exact
case-insensitive trade, insurance_status and optional as_of date,
composable with existing company search/include_inactive. Status
uses ACTIVE policies only and reuses verified vendor_insurance._status
(expired, within 30 days inclusive, upcoming, current, missing).
When multiple active policies exist, precedence EXPIRED >
EXPIRING_30_DAYS > UPCOMING > CURRENT; this is a review/alert
priority, not verification of coverage. No active policy is MISSING.
No historic snapshots are persisted, as_of is only a date-relative
interpretation of CURRENT recorded policy metadata. Archived
insurance excluded from status. SQL EXISTS predicates are correlated
to same-org Vendor and only after org ADMIN/OWNER + PEOPLE.VENDORS
authorization. Insurance metadata loaded in one scoped query
for at most 1000 vendors, guard 10000 active policies; no policy
numbers, carrier secrets, W-9s, bank data, GL writes or bills modified.
VendorOut directory summary includes status and nearest relevant
expiration, single-vendor detail otherwise unchanged.
Customer /dashboard/vendors adds trade, status and reference date
controls plus at-a-glance status/expiration per company.
Three regression tests validate status boundary, mixed policies,
foreign org, role/menu revocation, no-store, no GL posting and
invalid oversized trade filter.

NEXT original Phase 4: real Vendor link on Bills, then WorkOrder
vendor assignment/picker. Bill currently retains original free-text
payee_name and optional payee_user_id. Do NOT auto-match historic
payees by text, conflate Vendor company with UserRole.VENDOR, or
change GL amounts/history. Introduce nullable vendor_id FK, validate
active same-org Vendor on new bills, persist in same atomic posting,
retain original immutable payee_name snapshot, render choice in bill
creation UI, inspect existing listing and recurring/reversal behavior.
Do not silently mutate old rows; include migration guards, scoped
tests and full six-job CI. Then work order vendor link independently
from assigned_to_id crew user; preserve existing crew assignment
lifecycle and property access authorization.

## Phase 4 Bill company picker and link — VERIFIED 2026-09-27

Source/migration/regression tests:
7a8d30733480a31fb476391a923759d92242c043.
Customer New Bill picker:
5064b41a2f996d783fd25346a476c0a55c1b4a5a.
CI 36339328334 SUCCESS six jobs, 599 backend passed,
3 deselected, 11821 warnings in 131.97s; authenticated
browser E2E 3 passed in 9.70s; frontend/platform admin/
security/staging green. Existing browser E2E generic smoke,
not new-Bill vendor selector-specific test.
Superseded source-only run 36339303676 was cancelled;
no invented test result.
Manual Alembic migration b0c2d4e6f8a1 adds nullable Bills
vendor_id -> vendors.id ON DELETE SET NULL with index.
Model tables remain 110. PostgreSQL/bootstrap/legacy path
and migration head guards succeeded. No data backfill,
old Bills.vendor_id remains NULL. No frozen docs/ or
planning parity mutations.

BillCreateIn.vendor_id optional positive integer and
BillOut.vendor_id optional. New /dashboard/accounting/bills/new
picker lists only authorized active vendor companies via
GET /api/vendors. If user lacks PEOPLE.VENDORS or list
is unavailable, existing manual-payee entry continues.
Choosing a company sets/stops edits of payee_name
snapshot, and sends explicit vendor_id. Backend
post_bill validates active/not-deleted, same-org
Vendor and active/not-deleted ADMIN/OWNER user
with PEOPLE.VENDORS permission BEFORE original GL
posting; payee_name must match current selected
vendor company to avoid silently linking an unrelated
payee. Foreign/inactive/name-mismatch or permission
revocation fails before GL writes. No inference
from Bill.payee_name, no auto-link on old entries,
no UserRole.VENDOR contact substitution.
Bill vendor_id is recorded in same original bill
write; original paid expense/AP and amount posting
are untouched. Original payee_name remains a
historical snapshot if Vendor company is later
renamed/deactivated. Reversal mirror inherits vendor_id
without revalidating deactivated historic company.
Three focused tests cover original and reversal,
cross-org/inactive/name/permission fail closed before
GL, manual payee compatibility and no implicit matching.
No tax-profile links, bank info or special vendor
payment calculation introduced.

NEXT Phase 4: a real WorkOrder vendor company link/picker,
separate from assigned_to_id crew user and existing
work-order status/crew assignment. Inspect current
WorkOrder/WorkOrderUpdate schemas, router authorization,
UI route availability and company list permission.
Do not introduce vendors as UserRole.CREW or alter
existing crew assignment history. Restrict assignment
to authorized same-org staff with PEOPLE.VENDORS;
validate active same-org Vendor, preserve property/org
scope. Existing app may lack a customer WorkOrder
management screen; do not call a backend-only link a
completed user-facing picker. Include relevant safe
customer selection interface, focused regression
tests and migration guards. No accounting/GL writes.
Then return to original Phase 4 Contacts/Tags and
other tasks in dependency order.

## Phase 4 WorkOrder vendor company association — VERIFIED 2026-09-27

Backend model, scoped staff GET/POST, migration and regression tests:
c14e3c7d0a8a08257e9177247c56a7d1093424fd.
Authenticated staff vendor picker and link from vendor directory:
b90fd3deab170009e5b577f90f085ff98e034630.
Final GitHub Actions run 36339917953 SUCCESS all six jobs;
backend 601 passed, 3 deselected, 11898 warnings in 72.39s;
browser E2E 3 passed in 8.96s; frontend lint/typecheck/
production build, platform admin, security, staging all passed.
Browser E2E is existing authenticated smoke, not a
dedicated vendor-selector click test. Earlier superseded CI
run 36339883696 was not represented as the final green run.
Migration c1d3e5f7a9b0 adds nullable work_orders.vendor_id
-> vendors.id ON DELETE SET NULL, index; 110 model tables
unchanged. No historical auto-link, financial posting,
crew assignment or status mutation. No frozen docs or
parity mutations.

Existing /work-orders routes and crew assigned_to_id
lifecycle preserved exactly. Separate admin/owner-only
GET /work-orders/vendor-assignments and
POST /work-orders/{id}/vendor require active same-org
actor, PEOPLE.VENDORS plus MAINTENANCE.WORK_ORDERS
menu permission. Only active, nondeleted, same-org
company may be linked; cross-org WorkOrder/vendor IDs
fail closed. Finished CLOSED/CANCELLED WorkOrders
cannot change link. All writes log WorkOrderUpdate
and an immutable audit event in same transaction;
idempotent repeat selection does not duplicate audit.
Response deliberately excludes tenant name, entry
instructions, photographs and vendor private details.
Customer /dashboard/work-orders/vendor-assignments
lists scoped work orders and the authorized active
company selector, with explicit unlink; also linked
from /dashboard/vendors. The picker does NOT dispatch
a vendor, grant portal access, generate contracts,
or alter crew assignments, costs or GL.
Two regression tests prove link/unlink, audit,
tenant/manager denial, foreign company/workorder
denial, archived/finished/permission revocation,
inactive actor and GL non-mutation.

NEXT original plan Phase 4 People — Contacts / Tags:
- Contacts (non-vendor, non-tenant), then Universal
  Tags, then People import/export.
- Current repo has User accounts with role TENANT,
  OWNER, VENDOR, etc., and distinct Vendor COMPANY.
  Contacts must be an org-owned non-login directory,
  not fake User accounts or a second Vendor company
  collection. Inspect real existing roles and universal
  notes/attachments/permissions before implementation.
- Tags must be scoped universally to authorized
  entities, not raw cross-org table references or
  user-controlled arbitrary SQL; import/export later.
- Keep hybrid capability gating and immutable audit,
  active actor, org scope and exclusion of W-9/tax
  data from general exports. Include tests and
  verify full six-job CI. No extra docs/ changes.


## Phase 4 Contacts directory — VERIFIED 2026-09-27

Backend/model/migration/regressions b91ec3c38055272ae97a81a2e16630e87cd98ac7;
customer UI be1d1f84cac32a136202e8e17651161a63316fd3;
existing browser E2E test-only race correction
a607c8c370fa42f44e897a34a7667dd46c30ce69.
Full source CI 36340860778 SUCCESS all six jobs:
backend 604 passed, 3 deselected, 11960 warnings in 133.93s;
authenticated E2E 3 passed in 10.77s; frontend
lint/typecheck/build, platform-admin, security, staging-config green.
Initial CI 36340447416 backend 604 passed, but browser E2E
failed existing Features "Map view" toggle reload test because
it reloaded before the optimistic PUT response; test-only correction
awaits the actual successful PUT before reload. No Features
implementation changed. Earlier superseded runs cancelled.
E2E generic smoke, not dedicated Contacts UI interaction coverage.

Alembic d2e4f6a8b0c1 creates one contacts table,
111 expected model tables; bootstrap/legacy/PostgreSQL guards green.
Independent organization-owned non-login Contact PERSON/BUSINESS
with recorded name, company, email, phone, job title, mailing address.
No automatic User, Vendor, Bill, tax-profile or W-9 links.
Authenticated GET/POST/PATCH/DELETE/restore /api/contacts,
admin writes, ADMIN/OWNER/MANAGER permitted read with PEOPLE.CONTACTS;
nonstaff denied, inactive/deleted actors denied, cross-org IDs 404.
Bounded case-insensitive search, soft deactivation/restore,
no-store reads, append-only audit without contact PII.
Frontend /dashboard/contacts is preexisting PEOPLE.CONTACTS
menu destination. Form/directory supports add/edit/search/archive/
restore; unauthorized writes blocked by backend. Three focused
tests cover isolation, roles, revocation, audit, input validation
and no user/vendor mutations. Frozen docs/ and planning parity unchanged.

NEXT original Phase 4: Universal Tags, then People import/export.
Reuse verified generic entity_notes.resolve_note_target for
organization/permission/property scope and explicit safelist
of supported target entities; do not allow arbitrary table names,
tax data or cross-org targets. Tag definitions and scoped link
rows must be durable, audited and duplicate-safe. Keep staff
target permissions and user-visible picker on actual entities.
Existing Contacts non-login records should use PEOPLE.CONTACTS
when resolving generic notes/tags for assigned managers.
No GL/posting mutation, no tax identifiers or unencrypted W-9s.
Do not invent generalized bulk imports before tags verified.


## Phase 4 Universal Tags and Contacts CSV transfer — VERIFIED 2026-09-27

Universal Tags source 73d4cceae74c44b1fd45afe18368cd7514706039.
CI 36341415211 SUCCESS all six jobs: backend 607 passed,
3 deselected, 12069 warnings in 102.64s; E2E 3 passed
in 8.78s; frontend, platform admin, security, staging green.
Added tag definition/association models, migration and tests;
retained explicit target allowlist, org/member property scoping,
no tax/secret entities, audited idempotent links, and reusable
Contact/Vendor TagPicker. Do not rebuild tags.

Contacts CSV source 0062cc22834129c1998c2320e5f78cad50b9d1c8.
CI 36347187712 SUCCESS all six jobs: backend 612 passed,
3 deselected, 12151 warnings in 137.77s; authenticated
browser E2E 3 passed in 8.76s; frontend lint/typecheck/build,
platform admin, security, staging config all green.
Generic E2E smoke only, not a dedicated file-upload browser flow.

Files: backend/app/services/contact_transfer.py,
backend/app/routers/contacts.py, backend/tests/test_contact_transfer.py,
frontend/src/components/contacts/ContactTransferPanel.tsx,
frontend/src/app/dashboard/contacts/page.tsx.
Exports only active org Contacts via the canonical server
ReportPayload/CSV formula-escaping renderer. Requires live
PEOPLE.CONTACTS plus release.reporting.export, 1000-row ceiling,
no-store/nosniff/download headers; excludes inactive/foreign
contacts, Users, Vendors and any tax or W-9 data.

Admin import is TWO-STAGE: server CSV preview, then explicit
confirmed commit using the matching org-bound CSV SHA-256 digest.
Limit 128 KiB/200 rows, explicit 12-field contact allowlist,
Pydantic validation; rejects unexpected sensitive/identity
columns, invalid emails/types, malformed rows, in-file and
org-existing email/name conflicts (including archived contacts).
Revalidates live admin/menu/org access and all duplicates before
atomic insert, and serializes org imports through FOR UPDATE on
PostgreSQL. Never edits/merges existing records or creates User/
Vendor accounts. Audit records count only, never contact PII.
Five focused backend tests cover no-write preview, atomic creation,
conflicts/format/digest, org scope, role/menu/export revocation,
CSV formula escaping and unaffected Users/Vendors. No migration:
Alembic d2e4f6a8b0c1 / 111 tables unchanged. Frozen docs/ and
parity unchanged. This is bounded independent Contacts transfer,
NOT general user, vendor, tax or bank-data import.

Original next feature after Contacts/Tags/import-export section:
Phase 4 Leasing Applications expansion (read original Section 18
and Phase 4 checklist). Current LeaseApplication model already
contains optional applicant_ssn as PLAINTEXT String and screening
results as Text, even though no application router currently exists.
Do NOT expose, serialize, log, duplicate, or write plaintext SSNs
via any new intake. The approved encrypted W-9 tax profile storage
is for tax forms, not a default applicant screening store. Scope
Phase 4 application onboarding to safe non-SSN fields and
verified org/property/applicant access first; sensitive income/
screening, payment integration, consent, secure deletion and
reporting require separate controls/provider workflows. Do not
declare a full online paid/screened application workflow until
implemented and verified. Preserve existing Lease/GL/accounting
semantics. No frozen docs/ edits without separate authorization.


## Phase 4 Rental Applications initial safe intake — VERIFIED 2026-09-27

Source 864bf2e02a80e1b2a4af58a0bdaa279b5f4f14a9.
Full CI 36347804741 SUCCESS all six jobs:
617 backend passed, 3 deselected, 12289 warnings in 99.42s;
authenticated E2E 3 passed in 9.03s; frontend
lint/typecheck/production build, security,
platform-admin and staging-config all green.
Five focused backend tests; generic E2E smoke not
dedicated applicant UI payment or screening tests.
No migration: head d2e4f6a8b0c1 and 111 tables.
Frozen docs/ / parity unchanged.

Added /api/leasing/applications and the existing
LEASING.APPLICATIONS menu destination
/dashboard/leasing/applications; applicant role
gets a direct link from dashboard home.
Applicants with active organization accounts can
create self-owned DRAFT applications for active
same-org property and optional matching active
unit, edit only own draft, and explicitly submit
to PENDING_PAYMENT. Submission DOES NOT charge
a fee; ApplicationPayment count remains unchanged.
No staff approval, screening, status PAID or lease
activation route was added. Scoped staff ADMIN/
OWNER/MANAGER can read only current org/property
applications with live LEASING.APPLICATIONS menu
permission; managers need active assignment.
Other applicants, tenants, inactive users and
foreign property/unit probes fail closed.
No-store read APIs, 200-row queue ceiling,
append-only status-only audit, no GL writes.

Safe serializer and schema never accept, return,
or write existing plaintext applicant_ssn, DOB,
screening_result, fee_amount or payment tokens.
Existing LeaseApplication still has an old
applicant_ssn String column in schema: no new
intake may populate it. Form only collects
applicant name/email/phone, optional preferences,
bounded occupant names and pet description.
This does NOT implement original complete online
rental application; missing current/previous
addresses, personal/financial data, fee payment,
signed consent, screening and review workflows.
Do not call it FULL Applications until verified.
No public listings integration yet: applicant
supplies a property/unit ID from property office.
Do not infer applicant consent or eligibility.

NEXT bounded original Phase 4 Applications work:
complete secure applicant details and application
fee flow with verified amounts, consent, user/org
scope, payment webhook integrity; no plaintext SSN.
Review existing Property/Unit application_fee,
ApplicationPayment and Stripe checkout/webhook
infrastructure. Keep payment status server-trusted
and do not silently treat pending as paid. The
next phase after Applications in original Section
18 is Lease Templates, then CRM/Prospects and
Guest Cards. Avoid starting new unrelated Phase 3.7
reports or rewriting previously verified contacts.

## Phase 4 encrypted application questionnaire and fee quote — VERIFIED 2026-09-27

Encrypted private questionnaire source
cbcc52bf710791abd721b8a63dc4bceb10c9b806;
CI 36348392919 SUCCESS all six jobs (623 backend passed,
3 deselected, 12484 warnings in 143.90s; E2E 3 passed;
frontend, platform-admin, security and staging green).
Migration f1e3a5c7d9b0 adds one organization-owned
application_private_details ciphertext table (114 expected tables).
Separate APPLICATION_ENCRYPTION_KEY; never fallback to ordinary
SMTP or tax keys. Applicant-only own DRAFT edits, applicant and
authorized scoped staff read, no-store responses; encrypted
address/employment/income, no plaintext SSN, date of birth, bank
information or screening. Generic notes/attachments cannot target
private details. No fee or GL change from this batch.
Real provider-backed screening is Phase 8, NOT included.

Fee quote source 8e751bed878d158501754ae3858f1047e39888ef;
CI 36359893698 SUCCESS six jobs: backend 626 passed,
3 deselected, 12590 warnings in 103.00s; E2E 3 passed
in 10.16s; frontend, platform-admin, security and staging green.
No migration: still f1e3a5c7d9b0 / 114 tables.
backend/app/routers/rental_applications.py
  GET /api/leasing/applications/{application_id}/fee-quote
frontend/src/components/leasing/ApplicationFeeQuote.tsx
frontend/src/app/dashboard/leasing/applications/page.tsx
backend/tests/test_rental_applications.py
Three new focused tests verify applicant/foreign-organization/staff
access, disabled/foreign unit and property safety, optional unit/fee
unconfigured behavior, negative fee rejection, zero-dollar quote,
read-only repeat and absence of any ApplicationPayment/GL/status
mutation. Quote displays only server-configured active unit fee
in USD and never assumes a property-only fee or an unconfigured
zero fee. No checkout URL or payment action. E2E is generic
authenticated browser smoke, not a dedicated payment-browser test.

The next original Phase 4 Applications batch must implement an
explicitly configured provider-backed payment attempt and safe
webhook/accounting lifecycle; use actual Unit.application_fee,
never browser-supplied amounts or fake PAID status. Existing
app/services/stripe_billing.py is for subscription billing
and its webhook must not be reused as an application-fee
event handler without separate event identity/verification.
Use one-time Stripe Checkout/payment mode, unique idempotent
attempts scoped to application/organization/applicant, signed
webhook and exact amount/currency/intent/session validation;
accounting must use the verified GL/receipt posting with no
duplicate receipt on replay. Deferred payments, refunds,
overpayment, zero fee, session expiry, provider unavailable
and legacy paid statuses need explicit treatment. Do not
turn on payment until provider credentials, webhook secret,
GL cash/income mapping and reconciliation work end-to-end.
Existing ApplicationPayment is legacy and has no org FK or
unique provider guarantee; inspect before migration. Never
claim a Stripe session alone means money received. Consider
explicit applicant consent/terms before charging. Existing
POST /api/billing/checkout-session is SUBSCRIPTION mode, not
the application fee route. No frozen docs/parity edited.
No IRS/Avalara external filing progress is claimed by this batch.

## Phase 4 fee preparation contract — VERIFIED 2026-09-27

Source af94f8afefd853a906c9bf19fc96819eab42c7fc.
Full CI 36360330500 SUCCESS all six jobs: backend
629 passed, 3 deselected, 12662 warnings in 133.73s;
authenticated E2E 3 passed in 10.10s; frontend,
platform-admin, security and staging green.
Migration f2e4a6c8d0b1 (after f1e3a5c7d9b0)
creates one application_fee_attempts table; 115 model tables.
Read-only Unit fee quote from prior batch still verified.

POST /api/leasing/applications/{id}/fee-preparation
is applicant-owned, pending_payment only, requires
a currently active org/property/unit and configured
positive server fee; rejects missing/unitless, zero,
negative, changed fee and foreign/staff access.
Request has only an idempotency key (extra fields
forbidden); DB unique application ID and PostgreSQL
row lock enforce one pending preparation per app.
Duplicate same key+amount returns same prepared record;
different key or changed fee returns 409. Receipt/Stripe
payment rows, GL, app PAID status and existing signed
webhook/subscription billing remain UNCHANGED.
Status PREPARED and checkout_available=false are
not payment authorization or money received.
App payment provider step still needs verified
merchant-of-record/funds destination: existing
Stripe billing session is SaaS SUBSCRIPTION mode,
not an authorized application fee merchant account.
No live fee checkout should reuse platform
subscription funds by default. Existing 1099 provider
credentials are unrelated. Added three focused
tests for idempotency, money nonmutation,
foreign/staff/disabled-unit scope, fee precision
and generic-attachment denial. No frozen docs
or parity changes.

Next safe fee-workflow batch: explicitly link a
staff-received APPLICATION_FEE Receipt already
posted through verified GL, with exact same-org
property/unit and amount, source reference
and non-reversed GL, admin + receipts and
applications permissions, duplicate prevention,
audit and reversal reconciliation. Do NOT
post a second GL entry, fabricate payment
or use frontend success as a receipt.
This is *offline receipt accounting only*;
online Stripe checkout still needs distinct
org merchant/provider configuration, webhook,
event idempotency and provider-confirmed funds.
Respect original Section 18 Applications;
external Stripe payments remain Phase 8
integration dependency until configured.


## Phase 4 offline application fee settlement — VERIFIED 2026-09-27

Source f364877dabe43757ea949d8d28e1d2682e3bebaa;
migration/reversal fix 4781ddc4e4dccbb8e6be99f032704aaa56a685d3;
isolated receipt fixture repair b149717b76a45be85a02584d26176bbb90048dd4.
CI 36361333281 SUCCESS all six jobs: backend 633 passed,
3 deselected, 12872 warnings in 144.57s; authenticated browser
E2E 3 passed in 9.85s; frontend, platform-admin, security, staging green.
Prior run 36361018433 FAILED; fix and new CI green; intermediate
36360963206 CANCELLED. These counts apply to verified source only.
Alembic f3e5a7c9d1b2 adds nullable unique
application_payments.receipt_id FK; 115 SQLAlchemy tables unchanged.

POST /api/leasing/applications/{id}/record-fee-receipt is admin-only,
requires live LEASING.APPLICATIONS + ACCOUNTING.RECEIVABLES
permissions and release.accounting.receipts.application_fee;
links an EXISTING, active, non-reversed, exact-fee, verified
APPLICATION_FEE Receipt already posted through immutable central GL.
Original Receipt must match current organization, property, unit,
applicant name, APP-{application_id} reference, income GL 4420
and active original GL transaction. Prepared attempt amount/ID
and applicant ownership are verified. Unique receipt FK prevents
reuse; one paid payment per application. Link changes applicant
status to PAID without duplicating GL or charging Stripe.

Existing reversal and NSF receipt posting now reconcile linked
application fee: payment status reversed, application back to
PENDING_PAYMENT, fee_amount reset and attempt REVERSED, all
transactional with the original accounting reversal. An
unsuccessful locked-period GL reversal leaves paid application
untouched. Focused tests verify scope, permission/gate revocation,
idempotence/reuse, exact amounts/receipt references and reversal.
No browser-supplied fee amounts, no card checkout, and no automatic
provider fee deposit. The online Stripe/provider integration still
requires authorized org-specific merchant of record, signed
webhook, reliable event reconciliation and provider-confirmed funds.

NEXT original plan Phase 4 Lease Templates: 3-level Template +
Addenda + Attachments; database-wide (same organization) or
per-property. Reuse entity attachments with lease-template target
permission and property assignment checks; exclude tax/SSN
content, draft versioning/immutable published copies where required,
no automated e-signature or tenant disclosure without approval.
Before coding inspect existing Lease/Property and template-related
models, menu permissions, Frontend navigation and docs Section 18.
Use bounded product code plus applicable tests and hosted CI.


## Phase 4 Lease Templates and CRM — VERIFIED 2026-09-27

Lease Templates backend 6faba5d9e34fdc6be255006c0a50739a6bf6a4ae,
customer UI 3e37cc8ae9238a278cf4c7fc35586c98797e865a;
CI 36364069609 SUCCESS all six jobs: backend 636 passed,
3 deselected, 12972 warnings in 109.56s; E2E 3 passed in 8.73s.
Migration f4e6a8c0d2e3 adds lease_templates and lease_template_addenda,
117 model tables. Three-level draft template/addenda/ordinary universal
attachment UI, organization-wide or property scope, manager property
assignment restrictions, admin writes, audit, bounded text validator.
No signature, tenant delivery, active lease or GL mutation. Existing
attachment service reused; no parallel store.

CRM backend 0fcc72f063a13d0aeb7c420d88aa9531e314a8cc;
customer UI 1e2713aa5c549af6c6fc00bfc8b6b879e4ae8647.
CI 36365456607 SUCCESS all six jobs: backend 638 passed,
3 deselected, 13033 warnings in 107.99s; E2E 3 passed in 10.74s.
Migration f5e7a9c1d3e4 adds leasing_prospects (118 tables), linked
to existing org Contact and active Property. Stages NEW, CONTACTED,
TOUR_SCHEDULED, APPLIED, CLOSED; marketing source, follow-up date,
org/assignment scope, admin/manager staff writes, scoped owner read,
archive, permission recheck, redacted audit and duplicate rejection.
Source marketing label is captured; a full attribution analytics engine
is NOT implemented. Frontend /dashboard/leasing/crm uses existing
LEASING.CRM navigation and Contact/Property pickers. No login
identity, Application, Lease, payment or GL mutations.
Backend CRM regression tests: 2; existing tests: 636 prior to CRM,
638 now. Browser E2E is generic smoke, NOT dedicated CRM flow.
Frozen docs/ not edited; parity planning statuses not advanced.

NEXT original Phase 4 task: Guest Cards. Inspect existing
Contact, Prospect, Property/Unit scoping before coding. Use a
scoped prospective-tour/guest record linked to an existing prospect,
not a public unauthenticated intake or automatic applicant account.
No SSN, payment, screening, signatures or automated outbound
messages. Include regression tests, hosted CI and handoff update.


## Phase 4 Guest Cards — VERIFIED 2026-09-27

Source model/API/migration/regression/customer UI
b5dc99a60559d0ddb5fcb9b8aecca6813e320098;
follow-up scoped serializer/query refactor
70a5f00ae506f74567060d208e9aa8a92733663d.
Full CI 36365992264 SUCCESS all six jobs: backend
640 passed, 3 deselected, 13110 warnings in 117.87s;
authenticated E2E 3 passed in 9.55s; frontend lint/typecheck/build,
platform-admin, security and staging all green.
Initial CI 36365973815 was superseded/cancelled, not verified;
only final source 70a5 has verified complete CI. Generic browser
smoke, not dedicated Guest Card browser interaction tests.
Migration f6e8a0c2d4e5 adds leasing_guest_cards; 119 model tables.

GET/POST/PATCH/DELETE /api/leasing/guest-cards and customer page
/dashboard/leasing/guest-cards linked from CRM.
Each staff-recorded card refers to an existing active same-org
Prospect/Contact/Property, optional active same-property Unit;
records visit date, attendance and bounded next-step enum.
Admin and assigned Manager may write; Owner may read within org,
nonstaff denied; live LEASING.CRM permission and active user
rechecked. Manager only sees assigned properties. A same-prospect/
day database unique constraint rejects duplicate records;
soft archive and append-only redacted action audit.
Does not create or submit a rental application, lease, payment,
login identity, tenant signature, external messages or SSN.
Two new focused backend tests for scope, unit/role/permission,
duplicate handling, archive and zero application/lease mutations.
No changes to frozen docs or plan parity status.

NEXT original Section 18 CRM subrequirement: marketing effectiveness.
The verified CRM captures marketing source and staff-maintained stage
but has no source effectiveness summary. Implement an explicitly
read-only per-source stage/count breakdown over authorized active
prospects, with clear warning that staff-marked stages are NOT
verified paid conversions, ad spend or real applications. Do not
infer marketing ROI without cost data or change GL/applications.
Then consult original Phase 4 checklist for next unverified work.


## Phase 4 CRM recorded marketing-source summary — VERIFIED 2026-09-27

Source 423d78f52e1f3628701099ff8eba7dbff972903b.
CI 36366800985 SUCCESS all six jobs: 642 backend passed,
3 deselected, 13172 warnings in 152.71s; 3 authenticated E2E passed
in 7.64s; frontend, platform-admin, security, staging-config green.
No migration: Alembic f6e8a0c2d4e5, 119 model tables.
GET /api/leasing/prospects/source-summary uses live LEASING.CRM,
org isolation, manager assigned-property visibility, active
property/contact/lead filters and bounded per-source/per-stage
aggregation. Staff-marked stage APPLIED is not verified submitted
Application; no ad-spend ROI, verified conversions or GL effects.
Frontend marketing-source table within the verified CRM page updates
after staff changes. Two focused backend tests cover scope,
archived/disabled targets, role/menu permission and nonmutation.
Existing E2E is generic smoke, not dedicated CRM analytics UI test.
No frozen docs/ or planning parity changes.

NEXT original roadmap after Section 18 leasing: Phase 4.5 compliance
umbrella (HOA, Affordable, Commercial, RUBs, Escrow) and separate
4.6-4.17 product-line subphases described in docs/PLAN_GAPS.md.
Start with bounded property RUBs tab / allocation readiness,
not a full tenant charge engine: existing PropertyUtility and
UtilityBill describe current utility setup/owner-paid bills, but
no verified RUBs allocation formula, meter readings or legal rate
rules yet. Require org/property role/assignment scope; do not
create charges, GL postings or pretend a utility bill is
allocable without explicit reviewed rules and period data.
Check frozen docs/PROJECT_MASTER.md Section 38/Compliance checklist
and docs/PLAN_GAPS.md C1-C4 READ-ONLY; never amend without approval.
Then proceed in original dependency order after hosted CI.

## Phase 4.5 RUBs inventory and bill-period diagnostics — VERIFIED 2026-09-27

Read-only readiness source ca07e0af4103b55425b26561641728f521b991ab;
CI 36367397250 SUCCESS six jobs (644 backend passed, 3 deselected,
13237 warnings in 152.05s; 3 E2E passed in 10.99s).
Period diagnostics source 54ad71a8ab2d2bb8aaeeaad27f97614707b71369;
CI 36368986607 SUCCESS six jobs (646 backend passed, 3 deselected,
13305 warnings in 151.20s; 3 E2E passed in 9.20s).
No migrations: f6e8a0c2d4e5; 119 model tables unchanged. Frontend lint,
typecheck, build; platform-admin, security, staging green. No frozen
docs or parity statuses edited.

Property > RUBs gated release.properties.rubs uses live PROPERTIES.ALL
permission, active org + property scope, manager current assignment,
no tenant/other-organization visibility. Shows active SHARED utilities
and counts recorded bills with complete, missing or reversed periods.
Second bounded batch counts exact duplicate intervals and overlapping
intervals (inclusive boundary dates), ignoring invalid/missing periods.
An overlap count flags each subsequent sorted interval intersecting a
previous interval; a duplicate count flags subsequent identical
start/end pairs. Such flags need manual bill review and are NOT an
allocation formula or assertion of billable expenses.
Two original + two extra focused backend regression tests verify scope,
gate/role denials, duplicate/overlap calculations, invalid periods,
sensitive account-number/bill-amount exclusion and no Charge/GL change.
The authenticated browser smoke is generic, not a dedicated RUBs
browser interaction test.

IMPORTANT: docs/PLAN_GAPS.md C4 schedules full ratio allocation,
meter reading, utility provider integration, reviewed tenant/owner
charges, true-ups and reports as NEW Phase 4.9, not completed Phase 4.5.
Do not mark full RUBs implemented from the readiness tab. Do not assume
any recorded bill is legally allocable without property jurisdiction,
lease disclosures and reviewed cost/meter/occupancy rules.

Original Phase 4.5 additional trust-account enhancements in
docs/PLAN_GAPS.md C7 trust interest, C8 bank positive pay, C9 provider
e-filing remain scheduled. Next bounded Phase 4.5 task can establish
explicit trust-interest policy/manual legal-review readiness scoped to
verified bank/GL mapping. Do not assume whether interest belongs to
tenant, state or housing fund from bank account type or geography.
No GL posts, bank movements, tenant interest payment or tax claims
without verified jurisdiction/lease rules and an approved posting path.
Then proceed in the original plan dependency order.

## Phase 4.5 trust-interest jurisdictional policy readiness — backend VERIFIED 2026-09-27

Source ed9d2d97cce994909798c6f413e2ed4b4247c116.
GitHub Actions run 36369555961 SUCCESS all six jobs:
649 backend passed / 3 deselected / 13393 warnings in 104.75s;
3 authenticated E2E passed in 9.90s. Frontend lint/typecheck/
build, platform-admin, security and staging passed.
Migration a7c9e1f3b5d0 after f6e8a0c2d4e5 adds
trust_interest_readiness; 120 SQLAlchemy tables. Existing
GL/bank posting, bank identities, checks and RUBs unchanged.
Three focused tests: same-organization and current active bank/GL
scope, user/menu/release gating, validation, audit redaction,
no account number exposure and no GLTransaction writes. Generic
browser E2E is NOT a dedicated interest settings interaction test.

GET/PUT /api/accounting/bank-accounts/{bank_id}/interest-readiness
reuse customer auth, ADMIN/OWNER and ACCOUNTING.BANK_ACCOUNTS
permission plus existing release.accounting.bank_accounts gate.
Valid active org-scoped bank and active org-mapped ASSET GL are
required. A unique bank/org readiness record stores staff-entered
jurisdiction, proposed interest recipient class (UNDETERMINED,
TENANT, STATE, HOUSING_FUND, OTHER) and bounded basis-reference
text. Proposed recipient other than UNDETERMINED requires BOTH
jurisdiction and reference; neither represents verified applicable
law or formal approval. API returns no routing/account numbers and
only a boolean noting a supporting reference was recorded. Audits
contain bank ID and manual-review flag, never reference contents.
All outputs truthfully require further legal review; both
interest_allocation_enabled and interest_posting_enabled are FALSE.
No interest rate, daily accrual, tenant distribution, escrow transfer,
payee tax assessment, or generated financial transaction.
This is a preparation contract, not a completed C7 trust-interest
accounting engine. Frozen docs/ and parity unchanged.

NEXT bounded UI: reuse Bank Accounts customer listing; expose
a restricted interest-policy review link/action for ADMIN/OWNER,
with a modal or embedded accessible component for each current
bank. Explain proposed handling requires independent jurisdiction/
lease verification and nothing is calculated or posted.
Use existing apiGet/apiPut; never show full bank numbers.
Then return to original Phase 4.5 PLAN_GAPS C7/C8 order:
interest accounting remains gated until jurisdiction rules and
posting contracts verified; bank positive-pay requires a bank-
specific verified issue/void file schema and user review.

## Phase 4.5 trust-interest customer bank review UI — VERIFIED 2026-09-27

UI/regression source a2da32a884a16ff9a1fa8adedc3b199810d19e36,
CI 36370090346 SUCCESS six jobs: 650 backend passed,
3 deselected, 13423 warnings in 115.57s; 3 authenticated E2E
passed in 9.15s. Frontend lint/TypeScript/build, security,
platform-admin, staging green. No migration: head a7c9e1f3b5d0,
120 SQLAlchemy model tables. Original bank account editing and
fund movements unchanged. Frozen docs and parity unchanged.

Bank Accounts customer page includes scoped ADMIN/OWNER-only
Interest review button behind existing bank_accounts feature.
frontend/src/components/accounting/TrustInterestReview.tsx uses the
verified GET/PUT interest-readiness API; shows recorded jurisdiction,
proposed beneficiary and supporting-reference existence.
Previously stored free-text reference is not exposed in responses,
and must be re-entered when changing a proposed recipient.
UI clearly says independent legal/jurisdiction/lease review is
required, and no interest calculation, payout or GL posting exists.
One additional focused backend test verifies Cache-Control no-store,
the active same-org mapped ASSET GL check and no GL activity.
Generic E2E smoke passes; it is NOT a dedicated interest dialog
interaction test. Existing C7 trust-interest accounting and statutory
disbursement remain pending until verified jurisdiction-specific
requirements. Do not imply a staff proposal determines legal ownership.

NEXT original PLAN_GAPS C8 positive-pay check-file requirements.
The app has verified issue/void check ledger and Check Register
but no verified bank-specific positive-pay file schema/format
or bank acceptance. Start with bounded per-bank issue/void
eligibility/preflight from verified Check/GL state, staff scoped,
no routing/account numbers in UI or unsupported bank-upload file.
Require a confirmed bank template and human review before a
bank-specific positive-pay file is labelled upload-ready.
Reusing an ACH or check-register CSV as a bank-approved positive-
pay file is NOT acceptable. No GL, check issue, void or bank
reconciliation mutation in a readiness preview.

## Phase 4.5 positive-pay bank preflight + customer UI — VERIFIED 2026-09-27

Preflight source 82844c94fad5d4ef7fd33ac2e0366055953320e1,
CI 36370656288 SUCCESS six jobs: backend 653 passed,
3 deselected, 13565 warnings in 123.50s; E2E 3 passed in 8.42s.
Customer bank review source 6fe873dfa466a33b478dc638c0196bbddb64c9e5,
CI 36371943676 SUCCESS six jobs: backend 654 passed,
3 deselected, 13612 warnings in 149.65s; authenticated E2E
3 passed in 9.31s. Frontend lint/typecheck/build, security,
platform-admin, staging passed. No migration: Alembic
a7c9e1f3b5d0 / 120 model tables. Tests added with both
batches. No frozen docs/ or parity changes.

Admin-only GET /api/accounting/bank-accounts/{bank_id}/positive-pay/preflight
requires active same-org bank mapped to active ASSET GL, bank
permission, release.accounting.check_printing and verified Check
Register permissions. Accepts optional check-date range, max 500
recorded checks, no-store response. Reuses the verified issue/void
GL provenance logic, flags missing recorded number/payee, returns
only check display attributes (never bank routing/account IDs).
Internal issue/void status is NOT bank clearing or acceptance.
No check, GL, bank reconciliation or other accounting mutation.
Customer Bank Accounts page now opens a gated ADMIN-only
Positive-pay review dialog with date filters, issued/void counts
and review flags, explicitly NOT_SUBMITTED and no export.
Check-date is ORIGINAL issue date, not necessarily void-action date;
this view is not an event-dated bank file or accepted bank template.
Generic E2E smoke passed; it is NOT a dedicated dialog browser test.

Original PLAN_GAPS C8 positive-pay file/export remains UNVERIFIED:
a bank-specific approved template/schema, event/effective-date
semantics, transmission method, reconciliation and human review
are required before any upload-ready file or bank integration.
Existing ACH CSV/NACHA/check-register exports MUST NOT be
presented as positive-pay bank files. No actual bank file, submission
or bank acceptance implemented; needs bank-supplied specifications.
This is an external dependency and does not block work on
independent original-plan Phase 4.6.

NEXT independent original phase: 4.6 Affordable Housing /
Section 8 / LIHTC per PLAN_GAPS C1 (read frozen docs only).
Start with bounded property-level program inventory linked to
current org/property, staff-scoped and release.properties.compliance
gated, explicitly descriptive, not HUD/LIHTC eligibility
certification. Do not infer eligibility, HAP amounts, AMI limits,
income, legal rates or applicant status. Add focused tests and UI,
CI verify, then update this root handoff.

## Phase 4.6 affordable-housing property program inventory — VERIFIED 2026-09-27

Source 8c20d48deab2ad5fdbe8c323d8409462bce77068.
Hosted CI 36372554518 SUCCESS all six jobs:
657 backend passed, 3 deselected, 13686 warnings in 142.67s;
3 authenticated browser E2E passed in 8.93s.
Frontend lint/TypeScript/build, security, platform-admin and
staging-config green. E2E is generic authenticated browser smoke,
NOT a dedicated Compliance tab interaction test.
Alembic b8c0d2e4f6a9 (from a7c9e1f3b5d0);
model table count 121 (previously 120).
New backend/app/models/affordable_program.py, schemas/affordable_program.py,
routers/affordable_programs.py and 3 focused backend regressions;
new frontend/src/components/property/AffordableProgramsTab.tsx and
enabled existing release.properties.compliance-gated Compliance tab.
Root init_db.py, app/main.py, and 3 migration guard tests updated.
Frozen docs/ and planning parity not changed.

GET/POST/PUT/DELETE /api/properties/{property_id}/affordable-programs:
scoped active organization/property, ADMIN/OWNER writes,
assigned MANAGER reads only, no TENANT/CREW access.
Live PROPERTIES.ALL and release.properties.compliance required.
Records bounded staff-entered program category (LIHTC,
Section 8 voucher/project-based, HUD other, other), label,
optional recorded agency and dates. Explicitly not a verified
HUD participation, LIHTC certification, eligibility, AMI/rent
limit, HAP payment, tenant admission or tax-credit assertion.
Distinct recorded labels per property, immutable action audit
(redacted to program type), soft archive, 101-result bounded read.
No protected household, income, SSN, application/lease,
Charge, GL or bank account changes. Tests verify org/manager scope,
live gates/permissions, uniqueness, date validation, lifecycle,
no-store, activity and accounting nonmutation.

NEXT Phase 4.6 dependency: intake for existing authorized CRM
prospects' recorded interest in a recorded property program.
Build a *staff-recorded interest register*, NOT an official
HUD/LIHTC ordered waiting list, eligibility determination,
program-specific preference/ranking/offer or public signup.
HUD's own occupancy guides require program/owner-specific
tenant selection policies; do not auto-rank or infer eligibility.
Reuse Prospect/Contact/property assignment and active program
scope; require both PROPERTIES.ALL / compliance feature and
LEASING.CRM permission before revealing contact names.
Do not add race/disability/household/income fields to generic
interest register or expose applicants across organizations.
Next full program-specific waitlist/selection workflows depend
on reviewed jurisdiction/agency tenant selection plans.
Reference: https://www.hud.gov/hud-partners/public-housing-occupancy-guidebook
and https://www.hud.gov/helping-americans/housing-choice-vouchers-guidebook .

## Phase 4.6 recorded program CRM interest — VERIFIED 2026-09-27

Implementation 67d4d5f15d10b0830a02702b453c68a98e5e9d45.
GitHub Actions 36373217097 SUCCESS all six jobs: backend
660 passed, 3 deselected, 13816 warnings in 139.87s;
authenticated E2E 3 passed in 11.28s; frontend,
platform-admin, security, staging-config all green.
Generic authenticated E2E, not dedicated Compliance-tab interaction.
Migration c9d1e3f5a7b0 adds affordable_program_interests:
122 model tables, previous b8c0d2e4f6a9/121.
No frozen docs/ or parity edit.

GET/POST/DELETE
/api/properties/{property_id}/affordable-programs/{program_id}/interest
and customer Compliance tab "Interest" panel link
current authorized CRM Prospect/Contact to existing active
same-org property program. ADMIN/OWNER may record/archive;
assigned MANAGER may read only. Each call enforces
PROPERTIES.ALL, release.properties.compliance, LEASING.CRM,
current active organization/property/program and Prospect/Contact.
No archived contact name is returned. Unique org/program/prospect
constraint, bounded list 200, no-store, append-only redacted audit,
soft archive, date recorded is NOT admission/priority. Three
focused tests validate lifecycle, cross-org/property scope,
assignment, CRM/compliance revocation and absence of
Lease/Charge/GL mutation. No income, SSN, household protected
fields, eligibility decisions, HUD waiting-list rank, electronic
submission, applicant status or automatic messages.
Existing generic notes/attachment resolver is dynamically
model-discovering; assess denying this new linked-contact entity
to prevent disclosure via a weaker access route. Follow with
focused regression and CI before adding further sensitive modules.

## Phase 4.6 property-program evidence-readiness index — VERIFIED 2026-09-28

Source e492a46356bc19a57c55f63fe9ad85a5e0b7d5c8.
Hosted CI 36378052654 SUCCESS all six jobs: 665 backend passed,
3 deselected, 13936 warnings in 165.90s; 3 authenticated E2E passed
in 9.62s. Frontend lint/typecheck/build, platform admin, security,
staging passed. Generic browser smoke, NOT dedicated evidence UI E2E.
New migration d0e2f4a6b8c1 following c9d1e3f5a7b0;
123 model tables (prior 122). No frozen docs/ or planning parity edits.

Scoped active org/property/program staff evidence-readiness API:
GET/PUT /api/properties/{property_id}/affordable-programs/{program_id}/evidence.
Reuse verified compliance _property/_item authorization (live gate,
PROPERTIES.ALL, staff roles, manager active property assignment).
Only ADMIN/OWNER may edit; assigned MANAGER may read. Fixed categories:
agency guidance, program agreement, property record index, inspection
coordination. Staff-controlled statuses NOT_RECORDED, FOLLOW_UP_NEEDED,
REFERENCE_IDENTIFIED and optional staff follow-up date. These are
only records of staff preparation, not verified document availability,
agency approval, HUD/HQS/LIHTC certification, income/rent eligibility,
legal deadlines or inspection results. No raw documents, household
information, protected applicant data, open-text notes, rent amounts
or GL/Charge/Lease mutation in the new table.
New frontend/src/components/property/AffordableEvidenceChecklist.tsx
under already verified customer Compliance tab; canEdit follows
existing ADMIN/OWNER UI contract. Generic notes/attachments resolver
explicitly excludes affordable_program_evidence because its access
boundary is narrower than ordinary entity notes. Three new regression
tests cover scoped lifecycle, manager cross-property/other-org denials,
feature/permission revocation, invalid certification-like statuses,
audit, generic-target denial and accounting nonmutation.

Next safe Phase 4.6 subtask: show a read-only scoped count/most recent
date for already explicitly staff-recorded unit inspections, reusing
backend/app/services/unit_inspections.py; require its own existing
REPORTING.ALL, PROPERTIES.ALL, PROPERTIES.UNITS and ADMIN/MANAGER
authorization as well as the compliance gate and property visibility.
Do not expose inspection findings/tenant information via compliance
summary or claim existing staff observations satisfy HQS, LIHTC or
other agency-specific inspection standards. Existing full
unit-inspections route/report remains unchanged. Add focused tests
for permission mismatch, scope, inactive units and nonmutation.
After that, program-specific agency/legal policies and secure
household document workflow must be verified before substantive
eligibility/certification or HAP posting. Original Phase 4.6 remains
IN PROGRESS, no official compliance workflows are complete.

## Phase 4.6 existing unit-inspection cross-reference — VERIFIED 2026-09-28

Source 87c2eaa9ba5a21f8cc461c92cf46aaf474cd8b46.
CI 36378605760 SUCCESS all six jobs; backend 667 passed,
3 deselected, 14005 warnings in 161.47s; browser E2E
3 passed in 11.00s; frontend, platform-admin, security and
staging green. No migration: d0e2f4a6b8c1, 123 tables.
Frozen docs/ and parity untouched. Generic browser E2E passed;
no dedicated inspection-cross-reference browser test.

GET /api/properties/{property_id}/affordable-programs/
{program_id}/inspection-summary reuses existing _property/_item
compliance scope and the INDEPENDENT verified
unit_inspections._scope permissions: ADMIN/MANAGER and
REPORTING.ALL, PROPERTIES.ALL, PROPERTIES.UNITS; managers require
active assigned property. OWNER/tenant/crew do not obtain
inspection access from compliance permission. Only total recorded
count and latest inspection date are returned, NOT unit IDs,
tenant information, private findings, conditions or report bodies.
Query excludes inactive/deleted units and other organizations.
Read-only; no UnitInspectionRecord, Lease, Charge, GL or other
mutation. Frontend evidence panel lets permitted staff cross
reference the existing unit inspection report. Clearly
property-wide and not attached to program or independently
verified: NOT an HQS/NSPIRE/LIHTC inspection or agency clearance.
Two targeted backend regression tests cover scope, owner denial,
permission revocation, excluded inactive units, program archive
and nonmutation.

Original roadmap Phase 4.6 C1 next covers LIHTC Form 8609 building
identification and eventually annual 8609-A. IRS confirms
building-specific agency-assigned BIN and distinct 8609 per
building (multiple allocations may involve multiple forms for
one BIN). https://www.irs.gov/instructions/i8609
Safe next bounded prerequisite: staff-recorded BIN registry per
existing LIHTC program/property, explicitly not a signed IRS
8609, agency allocation, eligible basis, credit certification or
tax return. Require scoped ADMIN/OWNER writes, assigned MANAGER
reads and regression/CI verification. Avoid storing TINs, credits
or sensitive Form 8609 documents in ordinary attachments.
Source must be reviewed again before any actual tax computation
or filing; 8609 is separate from the 1099 provider workflow.

HUD program inspection policy is date- and program-specific; HUD
notices include the revised HCV/PBV NSPIRE transition through
Jan 31, 2027, with Feb 1, 2027 as the revised compliance date.
This is NOT a universal program deadline and no hardcoded
inspection policy/automatic pass-fail has been added.
https://www.hud.gov/reac/nspire-notices

## Phase 4.6 LIHTC per-building agency BIN inventory — VERIFIED 2026-09-28

Product source 952261b3448400dc5c4d1742e5b4b70538c1e2af.
GitHub Actions 36379299678 SUCCESS all six jobs: backend 670 passed,
3 deselected, 14101 warnings in 156.13s; authenticated E2E
3 passed in 6.16s; frontend lint, typecheck, production build,
platform-admin, security, staging-config all green. Generic browser
smoke, not dedicated BIN form E2E. Alembic e1f3a5b7c9d2 (from
d0e2f4a6b8c1); 124 model tables (from 123). Frozen docs/ and
planning parity untouched.

Existing customer Compliance LIHTC program offers "Recorded LIHTC
buildings" panel. New affordable_lihtc_buildings model links org,
property and one LIHTC program to staff-entered building label
and agency BIN, with scoped unique constraint, archive/restore
and immutable redacted audit. Same approved ADMIN/OWNER write,
assigned MANAGER read and same-org active property/program plus
live PROPERTIES.ALL/release.properties.compliance gates. Non-LIHTC
programs cannot use endpoints; tenant/crew and cross-property/org
probes denied. Generic notes/attachments resolver excludes
affordable_lihtc_buildings. Three new focused backend tests cover
lifecycle, repeated BIN rejection, cross-scope probing, release/
permission revocation, invalid input and no Lease/Charge/GL change.

This is an inventory only. The app does NOT validate against housing
agency records, receive signed 8609s, establish qualified basis,
calculate a low-income housing credit, certify resident eligibility,
file IRS returns or submit anything to housing agencies.

IMPORTANT FOLLOW-UP: The current generic BIN input pattern is
deliberately conservative about TINs but overly permissive for some
syntactically invalid agency IDs. IRS Notice 88-91 and current
IRM 3.11.26 prescribe two-letter state prefix, 2-digit allocation
year (IRS also accepts 4-digit year representation) and 5-digit
agency sequence, with dashed examples CT-87-00023 or
CT-1987-00023. Correct validation without changing existing
tables and test malformed shapes; continue to label all BINs
STAFF-RECORDED, never agency verified.
https://www.irs.gov/irm/part3/irm_03-011-026r
https://www.irs.gov/instructions/i8609

## Phase 4.6 Form 8609 per-building reference readiness — VERIFIED 2026-09-28

LIHTC BIN format-source 6ae01cc927264273e5fc8d067da15bd6c45f3faa
already passed all six CI jobs (36379842520) when this session started;
the older handoff had not recorded its verified status. It normalizes
2-/4-digit-year agency BINs and prevents alias duplicates. No rebuild.

New readiness product a28a4dd6b46757a226ce5e8ecd683341b1e9502b;
test-only fix 8a480d05e21a842b1376b1f4d5e595fe58d687de.
First source CI 36382232239 backend 673 passed, 1 failed,
3 deselected: NEW regression mistakenly forbade org ADMIN reading
another same-org property; actual authorization was correct. Revised
test asserts ADMIN same-org access and still denies assigned MANAGER
outside their assigned property. Current CI 36382487436 SUCCESS:
all six jobs; backend 674 passed / 3 deselected /
14235 warnings in 162.82s; E2E 3 passed in 8.67s; frontend,
platform admin, security, staging green. E2E is generic browser
smoke, NOT dedicated Form 8609 panel interaction.
Alembic f2a4b6c8d0e3 from e1f3a5b7c9d2;
125 SQLAlchemy model tables from 124. Frozen docs and parity untouched.

New affordable_lihtc_8609_readiness table holds only one bounded
status per existing active LIHTC building (NOT_RECORDED,
FOLLOW_UP_NEEDED, REFERENCE_IDENTIFIED), org/property/program/building
FKs, timestamp and staff actor; UNIQUE(org,building). Backend
GET/PUT /api/properties/{property_id}/affordable-programs/
{program_id}/buildings/{building_id}/8609-readiness. It reuses
approved compliance authorization: active same-org property/program,
ADMIN/OWNER write, assigned MANAGER read only, release gate and live
PROPERTIES.ALL. No data on archived buildings, no Tenant/Crew,
no cross-org/property ID probes, no generic entity notes/attachments.
No-store GET, redacted append-only audit, regression tests for
lifecycle, authorization, revocation and Lease/Charge/GL nonmutation.
Existing Compliance LIHTC building panel adds a staff status selector.
Staff status is NOT an authentic agency-issued signed original,
allocation certification, owner election, IRS submission,
annual 8609-A, tax credit or verified claim. No document is uploaded.
Form 8609 may have MULTIPLE separate allocations per building;
the single readiness status is aggregate staff follow-up only, not
an inventory of separate authentic forms.
Current IRS guidance:
https://www.irs.gov/instructions/i8609
https://www.irs.gov/instructions/i8609a

Next safe bounded dependency: restricted agency-issued Form 8609
document *archive* under a new dedicated encryption key (no
fallback), scoped to active LIHTC program/building and restricted
ADMIN/OWNER access; staff provenance and immutable list/download
audit. Reuse proven encrypted tax-W9 streaming pattern, not generic
unencrypted attachments, but do NOT conflate IRS signed original or
one-time filing with staff-upload attestation. Allow multiple copies
per building for distinct allocations; avoid declaring eligibility
or calculating basis or credit. Require operator-configured key
before any PDF archive; do not commit key material. Test oversize,
invalid PDF, tamper, scope, role and nonmutation. Signed document
handling needs malware scanning before broad external sharing and
reviewed retention; never expose the raw PDF in generic reports.
After that, any annual 8609-A tracker must explicitly distinguish
acquisition/building vs rehabilitation allocations and tax years;
do not infer applicable fraction or credit from staff metadata.

## Phase 4.6 restricted encrypted Form 8609 staff-scan archive — VERIFIED 2026-09-28

Product source fb448c7b283d1e29950fe1290c5d9c70ca25d51f;
CI 36383165892 SUCCESS all six jobs: backend 678 passed,
3 deselected, 14379 warnings in 159.99s; authenticated
browser E2E 3 passed in 9.96s; frontend, platform-admin,
security, staging green. E2E is existing browser smoke,
NOT dedicated document upload/preview E2E. New migration
a3c5e7f9b1d4 from f2a4b6c8d0e3, 126 model tables from 125.
Frozen docs/ and planning parity untouched.

New encrypted table affordable_lihtc_8609_documents linked to active,
same-org property/LIHTC program and recorded building. Distinct
rows can record multiple separate scans/allocations for one BIN.
PDF ciphertext is stored in a dedicated database LargeBinary field,
encrypted by operator-supplied COMPLIANCE_DOCUMENT_ENCRYPTION_KEY.
No key is committed; settings validates the key is a separate
valid Fernet key and runtime fails closed with 503 if absent.
Never reuse app, application-income or tax-W9 encryption keys.
No user uploads are stored as plaintext multipart temp files.
POST streams bounded 5MB raw application/pdf body, validates
PDF framing, requires staff scan-review attestation and received date;
that attestation is NOT independent agency signature/authenticity
verification or Form 8609 issue/IRS filing confirmation. No
automatic PDF malware scanner: do NOT distribute scans to tenants,
generic notes/attachments, general report downloads or public URLs.
Backend GET list/POST upload/GET download under the existing
/api/properties/{property_id}/affordable-programs/{program_id}/
buildings/{building_id}/8609-documents path. ADMIN/OWNER only,
live PROPERTIES.ALL / release.properties.compliance plus
organization/property/program/building active checks and 404
cross-org/cross-property denials. MANAGER cannot download PDFs even
if allowed to read non-sensitive BIN readiness. All list/download/
archive actions create redacted immutable audit records; returns
use Cache-Control no-store, sanitized Content-Disposition and
no-sniff/sandbox download headers. Generic entity notes/attachments
expressly exclude this document table. Existing customer LIHTC
building panel opens a restricted archive subpanel for staff.
Regression tests cover multiple scans, ciphertext redaction,
PDF/tamper/key failure, role and tenant isolation, gate revocation,
immutable audits and no GL/Charge/Lease mutation.
This is staff-held evidence ONLY, not signed 8609 agency verification,
IRS submission, allowable tax credit, annual 8609-A or eligibility.

NEXT 4.6 safe original-plan C1 subtask: Annual 8609-A
reference-readiness index by existing LIHTC building + explicit
tax year and separate base/acquisition vs rehabilitation
record type (IRS 8609-A instructions distinguish the two).
Explicitly not credit calculation, filing, proof of a 15-year
compliance period, 8609 original verification or agency approval.
https://www.irs.gov/instructions/i8609a

## Phase 4.6 annual Form 8609-A staff reference tracker — VERIFIED 2026-09-28

Source 5b520d93aaa7a4307fb5e8533da552aea210cffd.
CI 36383794588 SUCCESS all six jobs: backend 681 passed,
3 deselected, 14488 warnings in 126.64s; authenticated
E2E 3 passed in 9.49s, frontend, security, platform-admin
and staging green. E2E is generic browser smoke, NOT
dedicated 8609-A interaction. New migration b4d6f8a0c2e5
after a3c5e7f9b1d4, 127 SQLAlchemy tables from 126.
Frozen docs/ and planning parity untouched.

New affordable_lihtc_8609_annual table is only one bounded
record for (organization, LIHTC building, staff-entered tax
year, allocation category); categories BUILDING_OR_ACQUISITION
and REHABILITATION, fixed statuses NOT_RECORDED,
FOLLOW_UP_NEEDED, REFERENCE_IDENTIFIED. Year 1987–2100
is a syntactic bound, not an IRS eligibility determination.
GET/PUT under existing LIHTC property/program/building
scope, manager assigned read only, ADMIN/OWNER write, live
permissions/gates, no-store read, redacted immutable audit.
UI links from existing Compliance LIHTC building index;
there are NO income, eligible basis, applicable fraction,
credit, filing, signed original or sensitive household fields.
Annual category values are staff follow-up metadata, not
a prepared or submitted Form 8609-A. Generic notes and
unencrypted attachments denylist includes annual table.
Three focused tests cover year/category isolation, audit,
cross-organization/property/role/revocation, bounds,
generic target denial and GL/Charge/Lease nonmutation.

IMPORTANT ORIGINAL C1 DEPENDENCIES: agency-issued forms and
staff scans are not authentic issuer verification. IRS 8609
and annual 8609-A require actual eligible basis, owner election,
applicable fraction, compliance history and potentially
separate rehabilitations; do not derive credit from this
tracker. Housing-specific HUD/LIHTC income certifications,
tenant selection plans, utility allowance data, rent
and jurisdiction requirements need reviewed agency policy.
No HUD/LIHTC eligibility, HAP, tax calculation or IRS
transmission has been delivered.

## Phase 4.6 compliance key rewrap + read-only status — VERIFIED 2026-09-28

Existing product commit 40317c96f7b564abce3483b088727c25c53a6b2b
already implements admin-only scoped Form 8609 historical ciphertext
key rotation. CI 36384377433 SUCCESS all six jobs. Do not repeat.

This session added read-only, bounded, audited rotation readiness:
source 8c5e2a0973b40e414a68f2b8242621324f0e1419 and test-only
direct-route invocation correction
a8adc7dc2f47a40085c1203b38dd2254d778a907.
CI 36412399420 SUCCESS all six jobs: backend 685 passed,
3 deselected, 14644 warnings in 167.94s; authenticated
E2E 3 passed in 9.57s. Frontend, security, platform-admin,
staging passed. Existing general browser smoke, NOT dedicated
rotation UI E2E. No migration, Alembic b4d6f8a0c2e5; 127 tables.

GET /api/properties/{property_id}/affordable-programs/{program_id}/
buildings/{building_id}/8609-documents/rotation-readiness
is ADMIN-only, rechecks the existing property/program/building gate,
live org/role/permission boundary, and reads at most 25 scanned
records per page. It validates ciphertext against the current and
configured historical keys; counts only current-key vs needing
rewrap, no decrypted PDF or key material leaves server/audit.
Fails closed on missing historical key, malformed/invalid scan,
scope probing or revoked permissions. Redacted immutable audit
event records status access. No documents, leases, charges, GL
or financial data are mutated. HTTP response has no-store.
This proves ONLY per-page/per-building readiness; old shared keys
must NOT be retired until all relevant buildings/organizations
and encrypted stores are audited. No generic raw document access.

NEXT UI BATCH: show the read-only paginated administrator status
inside existing restricted Form 8609 archive with explicit
cross-building/organization warning. Avoid exposing to OWNER
or MANAGER, who may have archive/readiness access but cannot rotate
keys. Existing backend authorization remains authoritative.

## Phase 4.6 administrator Form 8609 rotation UI — VERIFIED 2026-09-28

Source 82c8ede338b9030acfd993bbe6888eae7e07ddce.
Full CI 36413219901 SUCCESS all six jobs:
686 backend tests passed, 3 deselected, 14678 warnings in
146.61s; browser E2E 3 passed in 8.78s; frontend lint,
typecheck, production build, platform-admin, security and
staging-config SUCCESS. No migration: b4d6f8a0c2e5, 127
SQLAlchemy tables; frozen docs/ and parity unchanged.
Browser E2E is general smoke, NOT a dedicated rotation UI test.

Existing frontend/src/components/property/Affordable8609Archive.tsx
now exposes an administrator-only, manually requested, paginated,
read-only inspection of the VERIFIED backend rotation-readiness
endpoint. Admin role resolved from existing /auth/me; OWNER and
MANAGER do not see the control and backend remains authoritative.
Shows only per-building counts of scanned/current-key/pending;
does not transmit PDF contents or keys, does not initiate rotation,
and tells the user explicitly that each building/organization
must be checked before global historical key retirement.
After archive upload, status resets to avoid stale indication.
Added focused backend regression for empty archive pagination,
live permission revocation, no-store status and absence of
GL/Lease mutations.

NEXT Phase 4.6 original C1 safe prerequisite: extend existing
staff affordable_program_evidence AGENCY_GUIDANCE category with
bounded provenance of independently reviewed public agency guidance,
if this can be added without leaking sensitive household data,
turning staff links into legal certification, or duplicating
evidence/document stores. Consider scheme/host validation,
staff-check date, live org/program scope, permission revocation,
and no accounting mutation. Jurisdiction/agency-specific actual
eligibility and HUD/HAP rules still require verified authoritative
source specifications before enforcement. Do not claim the
provenance field proves a policy is effective or authoritative.

## Phase 4.6 staff public agency-guidance provenance — VERIFIED 2026-09-28

Source 3f2d5d4b60f9eb29ced0aa68c182e41fe51df0e1;
URL authority/backslash hardening d5b63d0310b008489cb645e9d1cc74ab16ea4245.
CI 36414139582 SUCCESS six jobs: backend 688 passed,
3 deselected, 14709 warnings in 181.86s, authenticated E2E
3 passed in 10.21s. Frontend lint, typecheck and production build,
platform-admin, security and staging success. Generic E2E,
NOT a dedicated public-guidance UI browser test.

Migration c5e7a9b1d3f6 from b4d6f8a0c2e5 adds nullable
source_url and source_checked_on to the EXISTING table
affordable_program_evidence. 127 model tables unchanged.
All frozen docs/ and planning parity unchanged.

Existing property compliance Program Evidence panel, not new
parallel evidence/document storage, now allows ADMIN/OWNER to
record an optional PUBLIC HTTPS agency-guidance URL and
staff-checked date ONLY in AGENCY_GUIDANCE category when a
staff reference is recorded. Assigned MANAGER may see its
property-scoped staff index but cannot write. Existing live
release/PROPERTIES.ALL/property/program/assignment scope reused.
Link is not fetched/parsed for authoritative legal compliance,
not an official effective policy, not an agency signature,
not a household record, not HUD eligibility, not an AMI or
tax-credit calculator. It may be inaccurate, outdated or fake;
the UI visibly labels it STAFF-SUPPLIED/UNVERIFIED.
Only HTTPS public host links accepted; reject private/intranet
hostnames, raw IPs, embedded credentials, nonstandard ports,
whitespace, backslash authority ambiguities, too-long URLs
and checked dates in the future. Do not log full link URL in
immutable audit: only boolean public_reference_present metadata.
No GL, Lease, Charge or protected household mutation.
Focused tests cover validation, role/org/property scope,
null-on-unrecorded, audit redaction and nonmutation.
No public policy legal verification has been performed.

NEXT: remaining Phase 4.6 C1 substantive program-dependent tasks
require real authoritative agency/jurisdiction eligibility,
income-certification/privacy, HAP and AMI source requirements.
These are NOT represented as completed or safe to automate
without those sources/contractual permissions. The independent
original roadmap Phase 4.7 C2 HOA foundation (association and
property scope, no dues/penalties/board governance yet) is
available to continue without fabricating HUD/LIHTC rules.
Reuse existing property/release/org authorization and audit.
Never post HOA fees or violate accounting locks from a
staff-inventory entry.

## Phase 4.7 C2 HOA scoped registry and property UI — VERIFIED 2026-09-28

Backend source d929d71c50b40849e0f5fa6849b294ca87a4780b;
UI + fourth regression source 38dee8344851cac33b1f792e16a529211db86782.
Full CI 36424060872 success for backend source: 691 passed,
3 deselected, 14790 warnings in 171.54s; 3 browser E2E
passed in 9.65s. Final UI/source CI 36425025893 success
all six jobs: backend 692 passed, 3 deselected,
14820 warnings in 172.29s; browser E2E 3 passed
in 10.15s; frontend lint/typecheck/build, platform admin,
security, staging all green. Browser E2E remains generic
smoke, not a dedicated HOA interaction test.
Alembic d6f8a0b2c4e7 after c5e7a9b1d3f6, 129 model
tables from 127. Frozen docs/ and planning parity unchanged.

Staff association and many-to-many property inventory in
hoa_associations + hoa_property_memberships. CRUD at
/api/hoa/associations (GET list/one, POST, PUT, DELETE).
Reuse existing hybrid release.properties.compliance and live
PROPERTIES.ALL permission, organization-isolation and active
property checks. ADMIN/OWNER write; MANAGER read only their
assigned active properties, with no empty association-name
leak. TENANT/CREW and deactivated users denied. Cross-org
association/property probes fail closed. Case-folded
org-unique names, soft archive, redacted append-only audit,
no-store reads; generic notes/attachments denylist excludes
the two new registry tables. Four focused tests cover scoped
CRUD, many-to-many membership, name/ID validation,
revocation, no GL/Charge/Lease mutations.

Customer property detail > Compliance now includes
HoaAssociationsPanel, within the existing compliance gate.
Owners/admins can record multiple property links, attach
current property to existing association, unlink, archive;
managers read assigned memberships only. Explicit UI notices
that the recorded association is NOT legal verification,
member consent, assessment authorization, dues, penalties,
board governance or a booked liability. It posts no finance.

Original Phase 4.7 C2 is STILL IN PROGRESS. Exact next
dependent subtask: an explicitly recorded HOA property
contact/member responsibility roster (reuse the verified
independent org-scoped Contacts directory, do not infer from
Property.owner_id or tenant identities) and draft recurring/
special dues assessment configuration subject to legal,
payer identity and central GL controls. No automatic charge,
GL posting, reserve transfer, violation, board vote or
IRS/regulatory certification from staff inventory metadata.

## Phase 4.7 scoped HOA Contact references and UI — VERIFIED 2026-09-28

Source 404e6dcccff779c63311018221544d8508d929ff;
TSX parser fix 8b25ab6240c7cd69c1708d28002f583b526af71c.
First CI 36426173436 exposed a new frontend parsing failure;
corrected source CI 36426366891 SUCCESS all six jobs:
backend 694 passed, 3 deselected, 14893 warnings in 175.75s;
E2E 3 passed in 9.63s; frontend lint/typecheck/build,
platform-admin, security, staging passed. E2E is generic smoke,
not dedicated HOA UI. Migration e7a9b1c3d5f8 after
d6f8a0b2c4e7, 130 model tables (was 129).
Frozen docs/ and parity untouched.

New hoa_contact_links is an explicit scoped reference to the
existing independently managed organization Contacts directory.
It is NOT proof of legal HOA membership, ownership, voting rights,
registered agent identity or dues responsibility. POST/GET/DELETE
/api/hoa/associations/{id}/contacts route, requiring live
association/property membership, org/active Contact,
PROPERTIES.ALL + PEOPLE.CONTACTS + compliance hybrid gate,
admin/owner writes, assigned manager reads only. Cross-org,
inactive and unassigned scopes fail closed. Per-property unlink
and association archive soft-disable contact references, so
relinked property cannot silently regain old contacts; explicit
staff action is necessary. Immutable redacted audit, no-store
read, generic notes/attachments denylist, no GL/Charge/Lease
changes. Two focused regression tests cover these contracts.
Existing property Compliance HOA panel now opens nested
HoaContactsPanel, with explicit no-liability message.
No tax identifiers, owner/tenant liabilities or payment
instructions inferred from simple contact references.

NEXT: user-entered DRAFT HOA recurring/special proposal
configuration, association/property scoped and read-only to
assigned manager. No true assessment, due date enforcement,
automatic charge, GL booking, reserve accounting or fine
without verified governing authority, recipient ownership/
payer obligation, board approval, accounting policies.

# Exact next work: continue original C2 safely

1. Read full root handoff; verify actual branch HEAD and latest CI.
   Latest verified product d061925d5e29dee69833d13dcb8f6aaf785c7479,
   CI 36436896287 SUCCESS (705 backend passed, 3 deselected,
   3 E2E passed). Verified migration c7e9a1b3d5f2 / 132 tables.
   No duplicate HOA registry/contact/draft implementation.
2. HOA staff observations and staff meeting planning are VERIFIED.
   Current pending bounded Phase 4.7 C2 batch is staff-only ARC
   project-interest intake (backend/UI, migration e9a1b3c5d7f0,
   134 tables), NOT an approved architectural request or notice.
   Fix CI before proceeding; do not touch legal violation/fine
   workflows until governing authority and jurisdiction rules exist.
3. Actual violation notice, statutory cure period, fines,
   hearings, dues/payer liability, board approval and reserve
   accounting require reviewed governing documents, applicable
   jurisdiction rules and explicit legal actor authority.
   Never infer liability or send notices from staff observations.
   Phase 4.6 substantive HUD/LIHTC legal calculations similarly
   remain blocked on authoritative jurisdiction/program data.
4. Commit source+tests, require all six CI jobs green, fix reds.
   Keep this root handoff current with actual SHA/results;
   frozen docs/, main and branch structure unchanged.

## Session start for successor

Continue ONLY yasirskhan/property-platform branch
chatgpt/checkpoint-005-safety. Read entire repo-root AI_HANDOFF.md
and verify HEAD/CI. Last VERIFIED source
711800ce4d02aa5c1e52f5703b8817740832c24e;
CI 36439808118 SUCCESS all six jobs: 711 backend passed,
3 deselected; 3 browser E2E passed. Alembic e9a1b3c5d7f0,
134 tables. Verified HOA association registry, contacts,
staff-only recurring/special assessment draft backend/UI and
unlink/archive integrity. Do not repeat those batches.
HOA staff observations and meeting planning are verified.
Staff ARC project-interest intake is VERIFIED. Do not repeat it.
Next original HOA C2 dependency is obtaining/reviewing actual
association governing documents, applicable property jurisdiction,
actor authority, notice/cure/hearing and reserve accounting rules.
Without these authoritative inputs, do NOT invent official HOA
violation issuance/fines, ARC decisions, board votes, reserve fund
postings or legal deadlines. Safe registries/drafts are already
implemented; do not add duplicate placeholder stores. Actual HOA
legal notices/fines and HUD/LIHTC eligibility need reviewed
governing/jurisdiction rules. Do not touch main/new branches or
unrelated frozen docs. Use GitHub CI after commit; refresh handoff
after verified batch. Do not request Work mode.

## Phase 4.7 C2 HOA assessment draft source — VERIFIED 2026-09-28

Backend source d993b1afa2905e626f8ba6af233c05f236d5313c;
test-fixture correction b78f8fd8569a3b0a3c95699d3461123cbdcd9c4a.
Initial CI 36427514427 FAILED four new-test fixture setup errors:
monkeypatch targeted the assessment router rather than the existing
HOA authorization helper. Corrected CI 36428959926 SUCCESS all six
jobs, 698 backend passed, 3 deselected, 14988 warnings in 151.75s,
3 browser E2E passed in 6.24s; frontend, platform-admin, security,
staging green. This is source verification, not dedicated assessment
browser interaction E2E. New migration f8b0c2d4e6a9, 131 tables.
Backend staff DRAFT recurring/special proposal API is available:
GET/POST/PUT/DELETE /api/hoa/associations/{id}/draft-assessments.
No APPROVED status, payer, payable/receivable, Charge, GL, notice,
assessment issuance, automatic billing, fines or reserve movement.
Organization and association property link, active staff assignment,
compliance gate and PROPERTIES.ALL permission rechecked live;
ADMIN/OWNER write, assigned MANAGER read, TENANT/CREW denied;
archived/unlinked records fail closed. Generic unencrypted notes and
attachments cannot target proposals. Audit metadata redacted.
No changes to frozen docs/ or planning parity.

## Phase 4.7 C2 HOA assessment customer UI — VERIFIED 2026-09-28

Source ead950a0b7dc0aa0bae18c44513db5ccbbbe28e2 added
HoaDraftAssessmentsPanel.tsx to existing property Compliance HOA panel
and one additional API contract test. CI 36429898691 SUCCESS all six
jobs: 699 backend passed, 3 deselected, 15017 warnings in
176.77s; 3 authenticated E2E passed in 9.19s; frontend,
platform-admin, security and staging passed. Existing generic
browser smoke, NOT a dedicated HOA draft UI interaction test.
The panel offers read-only manager viewing, ADMIN/OWNER create/edit/
archive of staff DRAFT amounts/frequency/dates, and explains clearly
that no legal assessment, payer, approved charge or GL is created.
No migration. Source head f8b0c2d4e6a9 and 131 tables remain verified.


## Phase 4.7 C2 HOA draft scope integrity — VERIFIED 2026-09-28

Source fe1449420ab89723973e4e3730ce48d917f58f36;
CI 36431000854 SUCCESS all six jobs, backend 700 passed,
3 deselected, 15059 warnings in 136.91s; 3 browser E2E
passed in 9.35s. No migration: f8b0c2d4e6a9 / 131 tables.
On association/property unlink or association archive, active
staff assessment draft assumptions are softly archived with
redacted immutable audit; a later relink cannot resurrect
obsolete amounts. Regression tests cover relink, archive,
per-org isolation, zero Charge/GL/Lease effects.

## Phase 4.7 C2 staff observation prerequisite — VERIFIED BACKEND + UI

This new source batch adds only organization/property/association-
scoped staff observations for possible HOA issues. It is NOT
an adjudicated violation, an issued notice, a cure deadline, a
fine, a legal obligation, a hearing or a GL/tenant charge.
ADMIN/OWNER write; assigned MANAGER read. Backend checks live
association membership, compliance release gate, org and
property scope, and PROPERTIES.ALL permission. Generic notes/
unencrypted attachments denylisted; audit metadata excludes
free-text details. Association unlink and archive soft-disable
old staff records so relink cannot silently reactivate them.
Migration c7e9a1b3d5f2 adds hoa_observations (132 model tables).
Focused tests assert no legal/finance fields and no GL/Charge/
Lease mutation. Backend source fixed duplicate migration-revision
ID at commit 60671d5869191c261f06e28149995e477c1fda12;
CI 36432576387 SUCCESS all six jobs, backend 704 passed,
3 deselected, 15165 warnings in 178.27s, E2E 3 passed in
9.02s. Customer UI source d061925d5e29dee69833d13dcb8f6aaf785c7479;
CI 36436896287 SUCCESS all six jobs, backend 705 passed,
3 deselected, 15194 warnings in 156.31s, E2E 3 passed in
8.14s. Generic browser smoke, not dedicated observation UI E2E.
Frontend lint/typecheck/build, security, platform-admin and staging
green. New HoaObservationsPanel in existing property HOA
Compliance section: ADMIN/OWNER create/edit/archive, assigned
MANAGER read-only. Explicit non-legal/no-fines/no-GL labeling,
no tenant notifications or charges. Focused additional regression
checks manager payload visibility and no unauthorized archive or
finance posting. Frozen docs/ and parity unchanged.
No frozen docs/ or planning parity changes in this batch.


## Phase 4.7 C2 HOA staff meeting planning — VERIFIED 2026-09-28

Source 0073e49ccf84d5e8b6bfe48c459c7b4a0bb8b025.
CI 36438320448 SUCCESS all six jobs; backend 708 passed,
3 deselected, 15297 warnings in 180.28s; generic authenticated
E2E 3 passed in 8.21s; frontend lint/typecheck/production build,
platform-admin, security and staging green.
Migration d8f0a2b4c6e9 from c7e9a1b3d5f2 adds
hoa_meeting_drafts (133 SQLAlchemy tables). Planning parity and
frozen docs/ untouched.
Association/property/org-scoped staff draft CRUD at
/api/hoa/associations/{id}/meeting-drafts; existing live
PROPERTIES.ALL and compliance release gate, staff role and
manager assignment authorization rechecked. ADMIN/OWNER writes,
assigned MANAGER reads, TENANT/CREW denied. One hundred percent
staff planning: title, proposed date and tentative agenda; no
official meeting notice, minutes, votes, board quorum,
board membership certification, fines, dues or GL effects.
Generic notes/attachments denylist applies. Unlink/archive
soft-disable staff drafts, no hidden resurrection on relink.
Redacted append-only audit, no-store reads, bounded records.
Customer property HOA panel includes HoaMeetingDraftsPanel.
Three focused tests cover CRUD, org/role/assignment/revocation,
forbidden governance fields, no GL/Charge/Lease changes and
unlink/archive. E2E is generic browser smoke, NOT dedicated
meeting UI E2E. Formal board portal is NOT VERIFIED.

## Phase 4.7 C2 ARC staff intake — VERIFIED 2026-09-28

Verified source 711800ce4d02aa5c1e52f5703b8817740832c24e;
full CI 36439808118 SUCCESS all six jobs: backend 711 passed,
3 deselected, 15400 warnings in 182.75s; browser E2E 3 passed
in 9.57s; frontend lint/typecheck/build, platform-admin, security,
staging all green. General browser smoke, NOT dedicated ARC UI E2E.
Migration e9a1b3c5d7f0 from d8f0a2b4c6e9 / 134 model tables.
Property/association/org scoped staff architectural-interest
intake GET/POST/PUT/DELETE under /api/hoa/associations/{id}/arc-intakes,
existing live PROPERTIES.ALL + compliance gate; ADMIN/OWNER write,
assigned MANAGER read, TENANT/CREW denied. No applicant identity,
issued application, decision/denial, permit, statutory review period,
fee, charge, GL or legal notice. Customer HoaARCIntakePanel in
existing property HOA Compliance section; staff-only captions.
Association unlink/archive soft-deactivates prior intake; relinking
does not resurrect. Redacted append-only audit, no-store reads,
generic notes/attachments denylist. Three focused tests cover
CRUD, cross-org/assignment/permission, input extra-field rejection,
audit and zero GL/Charge/Lease effects, and unlink/archive.
Frozen docs/ and planning parity unchanged.


## Phase 4.7 C2 dependency boundary after ARC intake — 2026-09-28

Three consecutive meaningful source batches in this session are VERIFIED:
- Staff observations backend source 60671d5869191c261f06e28149995e477c1fda12
  CI 36432576387 SUCCESS, 704 backend passed / 3 E2E.
- Staff observation customer UI source d061925d5e29dee69833d13dcb8f6aaf785c7479
  CI 36436896287 SUCCESS, 705 backend passed / 3 E2E.
- Staff meeting planning backend/UI source 0073e49ccf84d5e8b6bfe48c459c7b4a0bb8b025
  CI 36438320448 SUCCESS, 708 backend passed / 3 E2E.
- Staff ARC intake source 711800ce4d02aa5c1e52f5703b8817740832c24e
  CI 36439808118 SUCCESS, 711 backend passed / 3 E2E.

The original Phase 4.7 C2 still requires real HOA assessments,
violations, statutory notice/cure, fines, hearings, board portal
governance/meeting/vote records, ARC applicant/decision workflow,
reserve studies/fund accounting and governing document delivery.
These are NOT complete. Property manager's staff-only records do not
create association authority, property/owner payer liability,
tenant charges, voting eligibility, legal decisions or accounting
permission. Do not convert proposal/intake fields into legal action
until authoritative governing documents and jurisdiction-specific
rules are provided and approved, and finance is centrally posted
through the verified GL with lock/idempotency/owner isolation.
Project docs/ source-of-truth and parity remain unchanged. Last CI
only verifies general browser smoke; specialized HOA interaction
E2E is still needed before release.

Exact next responsibly actionable work: obtain/review the actual
HOA governing documents, HOA jurisdiction, service/notice rules,
authorized decision maker, who pays dues and legal approval/
reserve policies. If these are unavailable, record a genuine
legal/data blocker, do not fabricate policy or relabel safe drafts
as completed full workflows. Independent later phases should
follow the original dependency order; no unapproved roadmap edits.
