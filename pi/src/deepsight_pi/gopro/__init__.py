"""GoPro controller — factory + implementations."""

from __future__ import annotations

from deepsight_pi.gopro.base import GoProController
from deepsight_pi.gopro.mock_gopro import MockGoPro
from deepsight_pi.gopro.real_gopro import RealGoPro


def create_gopro(mock: bool = True, wifi_ssid: str = "", wifi_password: str = "",
                 wifi_interface: str = "wlan0", usb_iface: str = "usb0") -> GoProController:
    if mock:
        return MockGoPro()
    return RealGoPro(usb_iface=usb_iface, wifi_ssid=wifi_ssid,
                     wifi_password=wifi_password)
