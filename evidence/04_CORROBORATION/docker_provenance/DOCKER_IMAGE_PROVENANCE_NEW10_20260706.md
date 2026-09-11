# Docker Image Provenance: Ten Additional RoadmapBench Tasks

Date: 2026-07-06

Scope: ten additional RoadmapBench task images were retrieved through a mirror registry and imported into the local Docker image store. No model API calls were made, and no experiment rows were executed.

## Retrieval Boundary

- Requested operation: pull ten additional RoadmapBench Docker images through a relay/mirror path while avoiding the local proxy path.
- Docker daemon network pull used: no.
- Direct client path: Python registry client with proxy disabled plus `curl --noproxy "*"` for blob downloads.
- Mirror registry used for the new ten images: `dockerproxy.net`.
- Local import method: `docker load` from locally assembled Docker-save archives.

Important limitation: the first six images were imported during interrupted script runs before the script wrote its final JSON output file. Their local tags and image IDs are recorded below, but complete manifest/layer JSON is only available for the final four images.

## Newly Imported Task Images

| Task | Local short tag | Image ID | Size | Complete manifest/layer record |
| --- | --- | --- | ---: | --- |
| `dsl-2.2.0-roadmap` | `roadmapbench-dsl-2.2.0-roadmap:latest` | `sha256:a869ca76d397...` | 0.81 GB | no |
| `fal-2.0.0-roadmap` | `roadmapbench-fal-2.0.0-roadmap:latest` | `sha256:f674f6647bae...` | 1.04 GB | no |
| `fbr-2.42.0-roadmap` | `roadmapbench-fbr-2.42.0-roadmap:latest` | `sha256:25d85fbcc271...` | 0.56 GB | no |
| `fyn-2.1.0-roadmap` | `roadmapbench-fyn-2.1.0-roadmap:latest` | `sha256:378cd6dcebf3...` | 0.89 GB | no |
| `glz-4.0.0-roadmap` | `roadmapbench-glz-4.0.0-roadmap:latest` | `sha256:6a25c5532b14...` | 1.37 GB | no |
| `ktx-0.10.0-roadmap` | `roadmapbench-ktx-0.10.0-roadmap:latest` | `sha256:69fb0f15d188...` | 1.54 GB | no |
| `mko-4.1.0-roadmap` | `roadmapbench-mko-4.1.0-roadmap:latest` | `sha256:12f5bb1418b5...` | 1.06 GB | yes |
| `opt-3.0.0-roadmap` | `roadmapbench-opt-3.0.0-roadmap:latest` | `sha256:1b34f1a83c83...` | 0.83 GB | yes |
| `plr-1.0.0-roadmap` | `roadmapbench-plr-1.0.0-roadmap:latest` | `sha256:6e80a84ded53...` | 1.45 GB | yes |
| `prm-5.0.0-roadmap` | `roadmapbench-prm-5.0.0-roadmap:latest` | `sha256:5e6eb5a0d388...` | 2.00 GB | yes |

## Complete Records For Final Four

| Task | Remote manifest digest | Local image ID after load |
| --- | --- | --- |
| `mko-4.1.0-roadmap` | `sha256:89416b06b424555f34b8d4bbc6f894ff699d4b903a0e5e5887258fdd9800639a` | `sha256:12f5bb1418b5b3d5f85cad500a240aea99c2b224f1cd4182a654fde6eab53b71` |
| `opt-3.0.0-roadmap` | `sha256:5371ee1af77a48c7e2bad937d9aeeb99c66052dbdca2022e77d7ecd0545a89d6` | `sha256:1b34f1a83c8351f999fc4a66ec8b77f43847a0bf37fa8d390ee44d9ace3ae7e3` |
| `plr-1.0.0-roadmap` | `sha256:e6637ff5527132d8cee78477348c0e68396ed719a7a6eb04c8924019b93bb2c3` | `sha256:6e80a84ded53f1d67369dd9846989b0752908bfdd3b37429b547aacf502c89e7` |
| `prm-5.0.0-roadmap` | `sha256:61da9cbd6f20256f66cd6f294e998afa6d7a1fab2038c7fa1e3587d5a989eda4` | `sha256:5e6eb5a0d388ae7d4466317cd867f91caca54e791ae6598abe2546501dd01eef` |

## Artifact Files

- `Artifact_Chain/tools/direct_mirror_pull_roadmapbench.py`
- `Artifact_Chain/DOCKER_MIRROR_DIRECT_PULL_NEW10_REMAINING4_20260706.json`
- `Artifact_Chain/DOCKER_MIRROR_DIRECT_PULL_NEW10_CONSOLIDATED_20260706.json`

## Interpretation

The local RoadmapBench image inventory increased from 10 unique task images to 20 unique task images. This is still below a 30-task target. The mirror route should be reported as digest/provenance-audited mirror retrieval, not as ordinary DockerHub direct pull.
