# DeepSight versus GoPro Quik (MISSION 1 PRO video scope)

DeepSight is not intended to reproduce Quik's editor, cloud, social, photo, or
timelapse features. Its target is the camera-control and video-transfer subset
needed by the underwater gimbal.

| Capability | DeepSight status | Notes |
|---|---|---|
| USB connection and camera state | Implemented | Pi forwards Open GoPro HTTP and preview traffic. |
| Wake after system power-on | Implemented by Labs configuration | `WAKE=4`; requires USB power re-application. |
| Power off a battery-backed camera | Not available over HTTP | Stop/finalize is implemented; a hardware power switch is still a separate concern. |
| Live view | Implemented | USB stream relayed through the Pi. |
| Start/stop video | Implemented | Stop waits for encoding and busy status to clear. |
| Video presets | Implemented | MISSION `GENERAL` group is discovered dynamically; gamepad preset cycling is video-only. |
| Video settings | Implemented, hardware validation pending | Runtime `supported_options` is authoritative; invalid combinations are not assumed from HERO13. |
| Battery, storage, remaining time | Implemented | SD status 54 is interpreted as kilobytes per Open GoPro. |
| Recording duration and health warnings | Implemented | Includes overheating and SD write-speed errors. |
| Browse, thumbnail, download, delete video | Implemented | Video files only. |
| BLE pairing/control | Intentionally omitted | Not required for this installation. |
| Photo and timelapse | Intentionally omitted | Not required for this installation. |
| Quik editing, music, cloud, sharing | Out of scope | These are app/service features, not camera-control API features. |
| HiLight tags | Planned | Open GoPro HTTP exposes file HiLight operations. |
| Camera clock synchronization | Planned | Open GoPro HTTP exposes get/set date-time. |
| Turbo transfer and resumable downloads | Planned | Recommended before treating export as Quik-like. |
| Real-camera setting matrix regression test | Required before deployment | Capture `/info`, `/version`, `/capabilities`, `/state`, and every displayed setting probe from the production MISSION 1 PRO. |

Official capability boundaries:

- [Open GoPro](https://gopro.github.io/OpenGoPro/) documents USB state,
  settings/mode, shutter, streaming, and media management for MISSION 1 PRO.
- [Open GoPro settings](https://gopro.github.io/OpenGoPro/docs/ble/settings/)
  explains why supported setting values must be queried dynamically.
- [GoPro Labs](https://gopro.github.io/labs/) provides the QR-based wake and
  sealed-installation behavior used by this project.
