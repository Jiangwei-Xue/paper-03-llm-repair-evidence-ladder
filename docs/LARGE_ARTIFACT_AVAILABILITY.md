# Large Artifact Availability

This GitHub source package contains the complete canonical analysis rows, retained
historical result ledgers, run configurations and plans, row-level E5/VCR indexes,
prompt-audit reports, and Docker identity/configuration metadata.

Complete per-attempt payloads are substantially larger. They include task-specific
prompts, raw hosted-model responses, parsed edits, generated patches, and full
verifier streams. Those materials are not included in this source package because
they require a separate archival deposit with their own size, access, and third-
party licensing review.

Public availability of such a separate complete raw-attempt deposit is
`NOT_VERIFIED` for this release. Consequently:

- the 2,400 normalized rows and manuscript statistics are fully recomputable here;
- row-ledger and replay-index identities are fully checkable here;
- the bundled VCR indexes prove retained row relationships and hashes;
- this package alone cannot dereference every historical raw-response artifact; and
- no claim is made that all hosted responses can be regenerated from an API today.

This boundary is intentional and machine-readable in `ARTIFACT_BOUNDARY.md`.
