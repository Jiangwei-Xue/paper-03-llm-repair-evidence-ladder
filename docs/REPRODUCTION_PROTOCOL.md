# Reproduction Protocol

## Reproduction claims

This package distinguishes four claims that must not be conflated.

| Claim | Public support |
| --- | --- |
| Recompute manuscript tables from canonical saved rows | Supported |
| Verify row hashes, replay links, and release closure offline | Supported |
| Re-enter historical Docker environments without external assets | Not supported by this package alone |
| Regenerate byte-identical hosted-model responses | Not supported |

## Environment

Offline replay requires Python 3.10 or later and the standard library. The
machine-independent environment contract is recorded in `PUBLIC_ENVIRONMENT.json`.
Regenerating the full derived analysis additionally requires the pinned package
in `requirements.txt`. Manuscript compilation requires the TeX tools listed in
`paper/README.md`.

## Offline replay

```sh
python3 replay_all.py
python3 docker/verify_metadata.py
```

The first command verifies the claim-bearing evidence chain. The second verifies
the 60-image identity and configuration surface. Neither command uses the
network, Docker, a model API, or hidden verifier data.

## Full derived analysis

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 reproduce.py
```

The output must end in `REPRODUCTION_STATUS=PASS`. Generated files are compared
with the checked-in manuscript inputs.

## Docker-assisted external rerun

A fresh container rerun requires resources intentionally outside this public
package:

1. task support files and verifier material obtained under the benchmark's
   applicable terms;
2. Docker/OCI images resolved to the digests in `docker/IMAGE_ROSTER.jsonl`;
3. a Docker-compatible runtime capable of executing `linux/amd64` images;
4. candidate patches or model responses selected under a declared rerun policy;
5. the runtime contract in `docker/RUNTIME_CONTRACT.json`.

The image metadata is sufficient to identify and inspect the historical runtime
surface. It is not a substitute for the omitted image layers.

## Model-output regeneration

Historical requests used hosted services. Exact regeneration can be affected by
provider-side model updates, serving implementation, routing, quantization,
sampling implementation, and availability. The package therefore supports
saved-evidence replay, not bitwise hosted-inference reproduction.

Any new model run must be treated as a new evidence stratum with its own model
identity, access date, request parameters, response metadata, UTC timestamps,
prompt hashes, and E5/VCR chain. It must not overwrite or silently extend the
historical estimator.

## Expected verification markers

```text
PUBLIC_SCIENTIFIC_EVIDENCE_INTEGRITY=PASS
H5_E5_VCR_REPLAY_STATUS=PASS
DOCKER_METADATA_STATUS=PASS
REPRODUCTION_STATUS=PASS
OVERALL_RELEASE_STATUS=PASS
```

Only checks that were actually run may be reported as passing.
