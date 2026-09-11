# Docker Image Provenance: 10 RoadmapBench Tasks

## Purpose

This record documents a direct mirror-registry provenance check for the 10 locally available RoadmapBench task images. No model API calls were run, and no experiment rows were executed.

The check avoided Docker daemon network pulls because Docker Desktop reported a daemon-level proxy. Instead, the registry metadata was fetched with a Python `urllib` client configured with `ProxyHandler({})`, which disables client-side proxy use. Docker was used only for local image inspection and local tag creation.

## Registry Path

Mirror registry:

```text
docker.1ms.run
```

Repository pattern:

```text
docker.1ms.run/znpt/roadmapbench-<task-id>:latest
```

## Result

All 10 mirror manifests were reachable through direct client access to `docker.1ms.run`. Each remote manifest digest matched the local Docker image ID / repo digest. Local mirror tags were created or confirmed without daemon network access.

| Task | Remote manifest digest | Status |
| --- | --- | --- |
| `dsl-2.1.0-roadmap` | `sha256:b58525c97d6f313bdcceade6eac6091eb7b957bdaf5f767fcaee936a9fcc3fb5` | matched; mirror tag present |
| `fal-1.3.0-roadmap` | `sha256:85fe912c973d9fbb97284e1599ffa333fd7f707abbb5ad664b9ea898a8e714cf` | matched; mirror tag present |
| `fbr-2.43.0-roadmap` | `sha256:ec14ff1dfcf49e75a9b4c611b3da4b71fc777cd533592512d447b4352b5082c8` | matched; mirror tag present |
| `glz-3.0.0-roadmap` | `sha256:5a644c408e59ce2e365390718feb1c678809acfc47686808663aaa126101595f` | matched; mirror tag present |
| `mko-3.0.0-roadmap` | `sha256:2e90fa87739e4306ae26e671963460c001b60a1086cb575ff9328250853e5cad` | matched; mirror tag present |
| `mko-4.0.0-roadmap` | `sha256:bd4c6edfdac0e281ba5c325a60b17a3d5b28eff7de75721374362e9f045e5313` | matched; mirror tag present |
| `opt-2.0.0-roadmap` | `sha256:6cbe24c3b766a47dc99d4465d0fc7df4f37b9493561983115d34a1eb1c15bc28` | matched; mirror tag present |
| `pyg-1.6.3-roadmap` | `sha256:952404c452439d6ff7801d85c3a071f4933f1d77b8eae5b184a2d61e51c20d38` | matched; mirror tag present |
| `rat-0.24.0-roadmap` | `sha256:eb9f6f50ba144d3ec67245904ff56d409053951379cae27573a65210c6c4abfd` | matched; mirror tag present |
| `tpl-3.2.0-roadmap` | `sha256:62768daacc7b7ebff77da8700d1b0b2156c0fef649567735bbdd279deee48072` | matched; mirror tag present |

## Boundary

This check verifies image identity for the 10 already-local RoadmapBench task images. It does not claim that additional RoadmapBench tasks have been downloaded. Future new task images should repeat the same process: retrieve or pull via mirror only when the content digest is recorded, compare it against the expected image identity, then record the task-to-image mapping in the artifact chain.

For public reporting, the appropriate wording is:

```text
RoadmapBench verifier images were retrieved or verified via a mirror registry and locked by content digest.
```

Avoid relying on mutable `latest` tags without digest records.
