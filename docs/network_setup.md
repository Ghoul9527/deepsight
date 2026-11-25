# Current development LAN

Updated 2026-10-15. Pi: `192.168.3.161/24`; gateway and DNS: `192.168.3.1`.
Host currently uses `192.168.3.158`. SSH: `tony@192.168.3.161`.

The Pi NetworkManager Wi-Fi profile `panta&mola_5G`
(`23fad6ff-3957-4c69-af7d-cbeaf619b065`) uses persistent manual IPv4 and
autoconnect. Wi-Fi reactivation was verified; no full system reboot was performed.
Reserve `192.168.3.161` for MAC `2C:CF:67:F0:4C:2D` on the router, or exclude
it from the DHCP pool, to prevent future address conflicts.

When changing LANs, update `network.pi_address` and `gopro.pi_url` in
`configs/host_config.yaml`, plus `network.host_address` in `configs/pi_config.yaml`
on both local and Pi copies. Also update the video relay destination in the Pi's
`/usr/local/bin/gopro-gateway-trigger.sh`. The Host IP is not fixed by this change;
if it changes, update the Pi's telemetry and video destinations together.

Backups on Pi: `/root/deepsight-network-backup-20261015/system-connections/`,
plus `.before-network-20261015` copies alongside the modified configs and trigger.
Other Wi-Fi profiles and GoPro USB subnets were preserved.
