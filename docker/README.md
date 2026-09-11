# Docker and Verifier Metadata

This directory documents the container execution surface without distributing
Docker image layers or protected verifier material.

## Files

- `IMAGE_ROSTER.jsonl`: one compact identity record for each of 60 task images.
- `IMAGE_CONFIGURATIONS.jsonl`: one complete retained `docker image inspect`
  configuration record for each image.
- `RUNTIME_CONTRACT.json`: mounts, commands, strict-apply rules, timeout logic,
  and pass criterion used by the historical runner.
- `source_records/`: structured historical pull records for the primary pool.
- `verify_metadata.py`: standard-library offline verifier for this directory.

## Verify

```sh
python3 docker/verify_metadata.py
```

Expected terminal marker:

```text
DOCKER_METADATA_STATUS=PASS
```

## Identity semantics

Registry manifest digests and local Docker image IDs identify different Docker
objects and can legitimately differ. `frozen_manifest_digest` identifies the
registry manifest fixed during retrieval. `historical_local_image_id` identifies
the post-load image configuration recorded by Docker. Neither should be replaced
with a mutable `latest` tag.

For a fresh external rerun, a reproducer should resolve each official reference
to the recorded manifest digest and verify the retrieved manifest before use.
The package does not automatically download images because registry availability,
third-party terms, and local network policy are outside the archived evidence.

## Configuration provenance

`IMAGE_CONFIGURATIONS.jsonl` is a retained historical metadata snapshot selected
by the image identities in the recorded pull ledgers. It is not a new live
inspection and does not contain image layers. The offline verifier checks that
the roster and configuration ledger contain exactly the same 60 unique image
identities.
