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

## Automatic Host registration

On a direct IPv4 LAN, configure the Pi address in the Host as above. Set
`DEEPSIGHT_HOST_PAIRING_KEY` to the same randomly generated 32-byte hex key in
the Pi service environment and in a protected Host key file (plain hex).
Set `network.host_pairing_key_file` to its path, relative to the Host config
file. The Host loads this key when it starts. For example,
generate it once with `python -c "import secrets; print(secrets.token_hex(32))"`.
Keep the key out of the repository. On the Pi use a protected systemd
`EnvironmentFile` for `deepsight-pi.service`.

Before enabling the Pi key, install the updated gateway script at the path
used by `deepsight-gopro-gateway.service` and replace its first argument (the
old Host IP) with `dynamic`. Preserve the camera IP and UDP port arguments.
If the Pi has a separate GoPro USB trigger, remove or disable the trigger's
legacy UDP socat launcher so it cannot take port 8554 on USB reconnect.
Restart the gateway service first to clear the old UDP relay, then start the
updated Pi service. The gateway still handles camera HTTP, and the Pi service
now listens for camera UDP. Set `network.gopro_address` and
`network.gopro_udp_port` to the camera USB IP and video port in use.

Restart the Host with the matching key. Pi takes the return address from the
WebSocket peer, then uses that address for both telemetry and video. Keep
UDP 5005 and 8554 reachable on the Host. A registration stays valid while its
session renews it every five seconds. A disconnect releases it, and missed
renewals expire it after 15 seconds. A second Host cannot replace an active
registration. On reconnect, the Host registers again, so its next address
takes effect without editing a config file or restarting Pi services.

To return to static mode, stop the Pi service, remove the pairing key from
both environments, restore the gateway's fixed Host address and any legacy
trigger configuration, and restart the gateway and Pi services. Verify
`network.host_address` also points to the intended Host.
