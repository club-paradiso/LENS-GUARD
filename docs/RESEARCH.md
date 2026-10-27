# Research and public artifact audit

Checked on 2026-10-27 (Asia/Seoul). This is an artifact and feasibility audit, not a successful reproduction of any paper's reported accuracy. LENS-GUARD contains an independent implementation; no upstream code or datasets are redistributed.

| Work | Public evidence checked | Reproducibility on this Mac without additional equipment |
|---|---|---|
| SCamF, ACSAC 2022 | Conference listing and full author-hosted paper; appendix A implementation | Not reproduced. Paper describes Galaxy S21+, Java app/C++ core, Android framework changes and custom driver/firmware monitor mode. No verified author code repository found in this audit. |
| Lumos, USENIX Security 2022 | Paper's `bit.ly/lumos-code` resolved to `rahul-anand/Lumos`; cloned and inspected files | Public code exists, but current artifact targets iOS 15 + Raspberry Pi 3/4 + monitor-capable USB Wi-Fi. Not a stock M1 installation. |
| CamLoPA, IEEE S&P 2025 | Public repository README and source file listing; remote commit inspected | Public Python code exists. Raspberry Pi 4B, Nexmon CSI and additional interfaces are required by its setup. Not reproduced under the no-equipment constraint. |

## SCamF

[Conference record](https://www.acsac.org/2022/program/papers/) · [author-hosted paper](https://rtcl.eecs.umich.edu/rtclweb/assets/publications/2022/acsac22-heo.pdf)

The paper “Are There Wireless Hidden Cameras Spying on Me?” studies encrypted Wi-Fi packet behavior, video encoding characteristics and user motion. Appendix A describes its layered Android implementation. A different GitHub project named `zhigang-yao/scAMF` concerns single-cell RNA analysis and is unrelated.

Checks: downloaded the complete paper, searched its text for repository/release references, searched GitHub repositories for `SCamF`, and searched the web for `SCamF source code` and `SCamF github camera`. These checks did not establish a public author-maintained camera implementation or reproducible package. This is a bounded negative search result, not proof that no code exists. Neither paper accuracy nor localization claims transfer to LENS-GUARD.

## Lumos

[Paper and presentation](https://www.usenix.org/conference/usenixsecurity22/presentation/sharma-rahul) · [source](https://github.com/rahul-anand/Lumos) · [paper mirror](https://elahe.web.illinois.edu/Elahe%20Soltan_files/papers/Usenix22_Lumos_cameraready.pdf)

Lumos studies multi-timescale wireless metadata and localization. The paper describes a MacBook prototype with a T265 tracking camera and a phone/Raspberry Pi implementation; a laptop alone is not equivalent to that complete setup.

The repository exists and was cloned at `c6bd2d3b6111a6a6eac1cc044e2d06de354802a9` (MIT license). Inspected `RPi/ssid_capture.py`, `RPi/localize.py`, `RPi/instructions.md`, and `Xcode/instructions.md`. Raspberry Pi instructions use old Node 8/Bleno components; Xcode instructions require an externally hosted Unity library. This audit did not verify that external binary or build the phone application. No trained classifier artifact or complete training/evaluation pipeline was identified by filename inspection; this is not a proof of absence within every generated file.

The capture script contains top-level logic to terminate other Python processes. It was **read, never executed**. Syntax parsing alone is not runtime reproduction. Hardware-dependent channel changes and capture also remain untested. Porting this artifact blindly would be inappropriate on the user's working Mac.

## CamLoPA

[Repository](https://github.com/CamLoPA/CamLoPA-Code) · [paper](https://arxiv.org/abs/2409.15169)

The repository exposes `camscan.py`, `location.py` and CSI processing helpers. Its setup calls for Raspberry Pi 4B with Nexmon CSI, an external communication interface and a monitor-mode interface. Its README also documents adapter-dependent camera visibility. Remote HEAD was `83b14c9686914e9cea22203a8461ffe6f4c10e9f`. Source visibility is verified; hardware execution and its published localization performance are not. LENS-GUARD does not implement CSI or claim location estimates.

## Design decision

A no-cost first prototype can reliably implement file decoding, bounded metadata aggregation, a transparent heuristic, provenance-aware UI and synthetic regression evaluation. Physical detection accuracy needs an authorized, labeled capture dataset and hardware verification. We therefore ship those software paths and expose their limitations rather than label a synthetic demonstration as a reproduction.

No upstream script was installed or executed, no third-party network was sampled, and no packet contents were decrypted. Downloaded papers and upstream checkouts remain outside the deliverable repository.

## Phase 2: traffic characteristics behind rules-0.2

Checked 2026-10-27. Text was extracted from the author-hosted SCamF PDF, the Lumos camera-ready PDF and arXiv 2409.15169 (CamLoPA). Pages are PDF page numbers. The quotes below were checked against the extracted text. The papers were read only; no artifact was run.

| Characteristic | Evidence | Used in rules-0.2 |
|---|---|---|
| Cameras upload continuously | CamLoPA p.4 §III-B: a device "continuously uploading data" is flagged as suspicious. SCamF §3.2 threat model: cameras "record and send/upload the victim's video in real time". | Uplink dominance. **No paper gives an uplink:downlink ratio**; ramp 0.55–0.85 is an assumption. |
| Using both directions helps | Lumos p.12 Table 6: incoming 89.73%, outgoing 83.18%, bidirectional 95.03% accuracy (device identification, their data); p.17: devices have "distinct incoming and outgoing behavior". | Motivates direction; accuracies do not transfer. |
| I frames are much larger and periodic | SCamF p.5: "I-frames are much larger than inter-frames"; p.8: "periodic peaks are removed to reduce the influence of I-frames". | Burst residual, periodicity, burst regularity. **No paper gives GOP length**; lag range 0.5–8 s is an assumption. |
| Frames split into full-size packets plus a remainder; cameras are not mostly full-size | SCamF p.4 §4.3 FU packetization; Table 1 average FU rate: camera 0.51 (range 0.09–0.91), VOD 0.95, download 1. "VOD and download services have high FU rates since they usually generate burst traffic." | Packet size mix rewards a mix of small and large packets, not a high full-size share. |
| Camera packet sizes and rates | CamLoPA p.10 §VI-B: average QoS data length "369 to 1050 bytes", "35 to 130 packets per second" for six cameras. | Generator rates for `camera_stream`. |
| Cameras keep a floor of traffic | SCamF p.5 §4.4: camera traffic "mostly shows a higher minimum traffic volume"; Table 1 camera minimum volume 5.2–241 kbps, average 52.5 kbps. | Sustained presence and session shape; `camera_low_rate` volume. |
| Motion raises bitrate | SCamF p.4: "Inter-frame sizes increase according to the movement in a scene". CamLoPA p.6 §IV-B: activity increases camera traffic. SCamF p.8: whole-flow bitrate tracking "works only for a few types of cameras". | `camera_motion` generator; not a scored feature. |
| Within-frame spacing is short | SCamF p.4: "The inter-packet interval in the same frame is much shorter than that in different frames" (θ ≈ 10 ms). | Not used: frame reconstruction is left for later work. |

Not found in these three papers: configured fps values (only SCamF's measured minimum FPS, average 26.4), GOP or key-frame intervals, motion bitrate magnitudes, a packet-size histogram, and video calls or cloud backup as confounders. SCamF's non-camera classes were VOD, download, picture and game. DeWiCam and codec standards were not checked in this phase. Reported accuracies (SCamF precision 0.935 and recall 1; Lumos 95–98% identification; CamLoPA 95.37% success, stated as 95.27% elsewhere in the same paper) apply to their hardware and data only.
