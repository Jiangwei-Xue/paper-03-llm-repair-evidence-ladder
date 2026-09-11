# H5 Artifact Manifest Contract

H5 denotes package-level identity and manifest closure in this release. It is
implemented by the following public, machine-verifiable surface:

1. `RELEASE_METADATA/RELEASE_MANIFEST.jsonl` records each released regular file,
   its SHA-256 digest, size, mode, and role.
2. `RELEASE_METADATA/SHA256SUMS.txt` provides the archive-root checksum view.
3. `RELEASE_METADATA/RELEASE_CONFIG.public.json` records the public build profile.
4. `RELEASE_METADATA/TOOL_PROVENANCE.json` identifies the release implementation.
5. `RELEASE_METADATA/BUILD_REPRODUCIBILITY_ATTESTATION.json` records the duplicate
   deterministic-build comparison.
6. `RELEASE_METADATA/DOCUMENTATION_COMMAND_ATTESTATION.json` records execution of
   the documented interfaces against the candidate archive.
7. `tools/VERIFY_ARCHIVE.py` rechecks safe members, manifest closure, checksums,
   metadata, and documentation attestations after clean extraction.

E5 is the row-level layer under `evidence/03_E5_VCR/`. Each row-ledger and replay
record has a canonical self-hash, and every replay record links to the matching
row-ledger record. The two layers are complementary: H5 closes the release object;
E5 closes the released claim-bearing row/replay identity.

`python3 replay_all.py --archive <ARCHIVE_PATH>` validates both the archive and the
2,400-row scientific evidence surface without contacting a model API or starting
Docker.
