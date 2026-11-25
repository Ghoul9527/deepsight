# GoPro MISSION 1 PRO integration

DeepSight now targets the fixed-lens **GoPro MISSION 1 PRO**. Do not use the
MISSION 1 PRO ILS firmware: it is a different camera target.

## Supported versions

| Component | DeepSight target |
|---|---|
| Camera | MISSION 1 PRO (fixed lens) |
| Minimum firmware with Open GoPro support | 1.10.00 |
| GoPro Labs firmware | 2.02.70 (2026-08-10) |
| Open GoPro capability schema | queried at runtime |

The host reads `/gopro/camera/info`, `/gopro/version`, and
`/gopro/camera/capabilities` at connection time. A firmware mismatch is logged
but does not prevent basic camera control, so a camera can still be diagnosed
before it is updated.

Official references:

- [Open GoPro supported cameras](https://gopro.github.io/OpenGoPro/)
- [Open GoPro HTTP API](https://gopro.github.io/OpenGoPro/http/)
- [GoPro Labs downloads](https://gopro.github.io/labs/)
- [GoPro Labs installation](https://gopro.github.io/labs/install/)
- [MISSION QR controls](https://gopro.github.io/labs/control/mission/)
- [Labs release notes](https://gopro.github.io/labs/control/notes/)

## Updating the physical camera

1. Charge the camera and use a compatible, freshly formatted microSD card.
2. Download **MISSION 1 PRO v2.02.70** from the official Labs downloads page.
3. Extract the downloaded package and copy its `UPDATE` folder to the root of
   the card.
4. Insert the card into the powered-off camera, then power it on and allow the
   update to finish without removing power.
5. Connect USB-C to the Pi and verify:

   ```bash
   curl http://CAMERA_USB_IP:8080/gopro/camera/info
   curl http://CAMERA_USB_IP:8080/gopro/version
   curl http://CAMERA_USB_IP:8080/gopro/camera/capabilities
   ```

The camera USB address is `172.2X.1YZ.51`, where `XYZ` is the final three
digits of its serial number. The gateway script also discovers `_gopro-web`
with mDNS and falls back to deriving `.51` from the USB subnet. Copy the
detected address into `gopro.real_host` in `configs/host_config.yaml`; this is
required because the camera validates the HTTP `Host` header.

## API behavior used by DeepSight

MISSION cameras return one flat `GENERAL` preset group (`2000`). Its entries
are top-level modes, and setting `239` selects sub-modes inside the active mode.
DeepSight therefore discovers the available presets and preserves an already
active video preset instead of forcing the HERO13 preset-group layout.

The current product scope is video only: photo, timelapse, webcam, Wi-Fi, and
Bluetooth controls are intentionally omitted. The control dialog uses a small
MISSION fallback option list for initial rendering, then replaces it with the
camera's context-sensitive `supported_options` response when a setting is
opened. This is necessary because resolution, frame-rate, lens, stabilization,
and profile compatibility changes with the preset and firmware.

The wrapper claims external control and sends keep-alive requests while
connected. It exposes recording duration, remaining video time, temperature,
SD write errors, storage, battery, and USB status. Stopping recording waits for
both encoding and busy state to clear before the file is treated as finalized.

## Power behavior

DeepSight does not use BLE. Labs `WAKE=4` plus USB power re-application is the
wake path. Open GoPro HTTP has no equivalent to the BLE power-down command, and
a battery-backed camera cannot be guaranteed off merely by removing hub power.
Before external power is removed, software must stop recording and wait for file
finalization. Physical hub/light power switching remains a separate hardware
function.
