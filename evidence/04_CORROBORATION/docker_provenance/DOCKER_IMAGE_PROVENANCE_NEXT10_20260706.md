# Docker Image Provenance: Third Batch of Ten RoadmapBench Tasks
Date: 2026-07-06
Scope: ten additional RoadmapBench task images were imported by direct mirror retrieval. No model API calls were made, and no experiment rows were executed. Ordinary Docker daemon network pull was not used.
## Result
The local RoadmapBench short-tag task image count increased from 20 to 30.
| Task | Successful mirror | Manifest digest | Local image ID prefix | Size | Record completeness |
| --- | --- | --- | --- | ---: | --- |
| `dsl-2.3.0-roadmap` | `dockerproxy.net` | `sha256:6f033a0c8207f4f3d1eea5082518912386f36a195f63e86c886b011ffb7ed4e2` | `sha256:fb95180a9cf8...` | 1.7GB | `complete_import_before_interrupted_json` |
| `fal-4.1.0-roadmap` | `dockerproxy.net` | `sha256:d60c072d1c8377215404bfaf5814d0c360af83b48d74cb0a70d06ccae0b28257` | `sha256:2da81720a1a5...` | 260MB | `complete_import_before_interrupted_json` |
| `fbr-3.0.0-roadmap` | `dockerproxy.net` | `sha256:1d3b3eab7774ec3406ca499a8cd851f426dbf173fceb05693e3d9590896619d5` | `sha256:45e73f2ce26e...` | 1.1GB | `complete_import_before_interrupted_json` |
| `fyn-2.7.0-roadmap` | `dockerproxy.net` | `sha256:9943231893d0d52b269fa74b526e0540d3db1419623d50fb444dea50374fbcb0` | `sha256:a65f62c6eba7...` | 1.27GB | `complete_import_before_interrupted_json` |
| `tpl-3.0.0-roadmap` | `dockerproxy.net` | `sha256:f30b4af83daadede914a91934e1ff64e7db2ec27d0b8368ed52287d840623076` | `sha256:7d8f1eed69a4...` | 338MB | `complete_import_before_interrupted_json` |
| `tpl-3.3.0-roadmap` | `dockerproxy.net` | `sha256:80fb4aa2dbf7551086d59528ebd4369abf4f3034ffc318496a0ffec3bc6dbc39` | `sha256:97879ceadde2...` | 340MB | `complete_import_before_interrupted_json` |
| `tpl-4.0.0-roadmap` | `dockerproxy.net` | `sha256:120bedd7b1732659eaea646347db631fb8f347e60253c8dcf722f39391e813b9` | `sha256:674dc2e5b8be...` | 340MB | `complete_import_before_interrupted_json` |
| `tpl-5.0.0-roadmap` | `docker.1ms.run` | `sha256:15d4f76538b43a99c9e26dd5cb60fd74bf72d799e0b107abfbea6e66ca0c675d` | `sha256:915eed540b19...` | 340MB | `complete_json` |
| `tpl-5.1.0-roadmap` | `docker.1ms.run` | `sha256:049ef3d98a806cddc26077c69e71f23dc6cb6c1fee081141c241b5a9ab1562d6` | `sha256:d9030c75ff29...` | 341MB | `complete_json` |
| `spc-3.5.0-roadmap` | `docker.1ms.run` | `sha256:8ae9c8a2cb66591f86b8b52a97fd0e7a5050fcd65ab53b30d02c24e00f155193` | `sha256:9cb2b447a2a5...` | 945MB | `complete_json` |

## Failed Or Replaced Attempts
- `pyg-2.6.0-roadmap`: large-layer direct transfer repeatedly stalled or failed over dockerproxy.net; not counted as imported.
- `rat-0.28.0-roadmap`: dockerproxy.net direct TLS failures before successful import; not counted as imported.
- `slt-1.14.0-roadmap`: manifest preflight failed in this session; not attempted as successful import.
- `ruf-0.12.0-roadmap`: manifest preflight later failed in this session; not counted as imported.
- `tpl-5.0.0-roadmap via dockerproxy.net`: blob direct transfer failed; successfully imported afterward via docker.1ms.run.

## Boundary
For all ten successful imports, the DockerHub official manifest digest and the successful mirror manifest digest are recorded as equal. Local Docker image IDs are recorded separately because image IDs/config digests are not the same Docker object as registry manifest digests.

## Source Files
- `Artifact_Chain/tools/direct_mirror_pull_roadmapbench.py`
- `Artifact_Chain/DOCKER_MIRROR_DIRECT_PULL_NEXT10_TPL_REMAINING2_1MS_20260706.json`
- `Artifact_Chain/DOCKER_MIRROR_DIRECT_PULL_NEXT10_FINAL1_1MS_20260706.json`
- `Artifact_Chain/DOCKER_MIRROR_DIRECT_PULL_NEXT10_CONSOLIDATED_20260706.json`
