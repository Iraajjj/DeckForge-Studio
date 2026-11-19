# DeckForge Studio — portfolio case study

**Problem.** A maker preparing multiple 78-card collections manually must inspect image dimensions, duplicated artwork, tarot symbolism, printer handoff geometry, guide QR codes, approvals, cost estimates and exports. Manual handoffs are repetitive and can produce expensive printing mistakes.

**Product approach.** Built a local-first Python application that tracks a canonical 78-card manifest, checks source image metadata, and generates reproducible review packages. V2 added an interactive offline gallery; V3 added human review and approval invalidation by SHA-256, physical-size proofs, supplier gates and cost estimates. V4 adds optional AI visual observations, factory-template registration, ICC colour transformations and a Windows executable release pipeline.

**Engineering evidence.** Automated pytest regression suite (local V4: 46 passing tests), QR and ZIP checksums, conservative filenames/imports, authenticated-only opt-in API usage, formal JSON schema validation, image colour-space conversion, registered PDF overlays, input validation and a Windows build workflow. Model output is always subject to human review; unconfirmed printer geometry blocks final approval.

**Honest status.** The original procedural 78-card demonstration deck passed local technical checks. The live external AI provider was not called (requires separate credentials and billing). A real printer dieline and paper/ICC approval have not been provided. A standalone Windows installer can be built via the included Windows workflow, but no native Windows binary was compiled here.

**Business impact to measure once deployed.** Time spent per 78-card review, technical defects found prior to supplier submission, reduction in failed exports, revision time, printer correction rounds and final landed cost accuracy. Do not claim actual time or cost savings without measurements.

**Portfolio framing.** Demonstrates AI integration under human control, automation, QA design, reproducible artifacts, printer integration, privacy boundaries and practical product delivery. Public examples use original art, not recognizable franchise assets.
