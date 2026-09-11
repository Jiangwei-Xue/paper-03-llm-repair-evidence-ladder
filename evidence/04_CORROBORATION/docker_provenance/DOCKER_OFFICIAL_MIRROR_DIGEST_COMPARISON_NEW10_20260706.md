# DockerHub Official vs Mirror Digest Comparison: Ten Additional RoadmapBench Images

Date: 2026-07-06

Scope: compare DockerHub official registry manifest digests against the `dockerproxy.net` mirror manifest digests for the ten additional RoadmapBench task images imported locally on 2026-07-06.

No model API calls were made. The check used Docker registry manifest requests with proxy-disabled command-line networking.

## Result

All ten official DockerHub manifest digests matched the mirror manifest digests.

| Task | DockerHub official manifest digest | Mirror manifest digest | Match |
| --- | --- | --- | --- |
| `dsl-2.2.0-roadmap` | `sha256:efe63119d4388e2b0d0e9397b7d95336844552f75ea90922b3447a2006f141aa` | `sha256:efe63119d4388e2b0d0e9397b7d95336844552f75ea90922b3447a2006f141aa` | yes |
| `fal-2.0.0-roadmap` | `sha256:92350c073bee31c5077d414995a5dcc530cef6ee4b7f625c58bf2c964ca7a598` | `sha256:92350c073bee31c5077d414995a5dcc530cef6ee4b7f625c58bf2c964ca7a598` | yes |
| `fbr-2.42.0-roadmap` | `sha256:32e684124fa85db3fbf5832235cd445f60194cf1a0ec60cc935835fef5a172bf` | `sha256:32e684124fa85db3fbf5832235cd445f60194cf1a0ec60cc935835fef5a172bf` | yes |
| `fyn-2.1.0-roadmap` | `sha256:8d6a3611115005d80a97262b121ad8eb7715c28c41340a28b468a3a2859cf1da` | `sha256:8d6a3611115005d80a97262b121ad8eb7715c28c41340a28b468a3a2859cf1da` | yes |
| `glz-4.0.0-roadmap` | `sha256:662e57f5738ee2a7dc3cf505e5805b4d5ad482abbdb659aaa48ba19b78025127` | `sha256:662e57f5738ee2a7dc3cf505e5805b4d5ad482abbdb659aaa48ba19b78025127` | yes |
| `ktx-0.10.0-roadmap` | `sha256:575b593008c776ae862f040e7944a2f3d77d65d9ff48029460c5f711d218fbc0` | `sha256:575b593008c776ae862f040e7944a2f3d77d65d9ff48029460c5f711d218fbc0` | yes |
| `mko-4.1.0-roadmap` | `sha256:89416b06b424555f34b8d4bbc6f894ff699d4b903a0e5e5887258fdd9800639a` | `sha256:89416b06b424555f34b8d4bbc6f894ff699d4b903a0e5e5887258fdd9800639a` | yes |
| `opt-3.0.0-roadmap` | `sha256:5371ee1af77a48c7e2bad937d9aeeb99c66052dbdca2022e77d7ecd0545a89d6` | `sha256:5371ee1af77a48c7e2bad937d9aeeb99c66052dbdca2022e77d7ecd0545a89d6` | yes |
| `plr-1.0.0-roadmap` | `sha256:e6637ff5527132d8cee78477348c0e68396ed719a7a6eb04c8924019b93bb2c3` | `sha256:e6637ff5527132d8cee78477348c0e68396ed719a7a6eb04c8924019b93bb2c3` | yes |
| `prm-5.0.0-roadmap` | `sha256:61da9cbd6f20256f66cd6f294e998afa6d7a1fab2038c7fa1e3587d5a989eda4` | `sha256:61da9cbd6f20256f66cd6f294e998afa6d7a1fab2038c7fa1e3587d5a989eda4` | yes |

## Interpretation Boundary

This comparison verifies that the mirror registry returned the same manifest digest as DockerHub official for these ten tags at the time of the check. It supports the claim that the mirror route did not change the task-image manifest identity.

Do not compare these manifest digests directly to local Docker image IDs. A local Docker image ID commonly reflects the image config digest after import, while the registry manifest digest identifies the manifest object. The paper/artifact claim should therefore report official-vs-mirror manifest digest equality and separately record local image IDs.
