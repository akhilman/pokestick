from collections.abc import Iterator

from .abc import Watchdog
from .device_id import DeviceId
from .watchdog_pro2 import WatchdogPro2

DRIVERS: list[type[Watchdog]] = [WatchdogPro2]


def init_device(device: DeviceId) -> Watchdog:
    for driver in DRIVERS:
        if driver.is_compatible(device):
            return driver(device)
    raise UnsupportedDeviceError("Unsupported device", device)


def list_devices() -> Iterator[DeviceId]:
    for driver in DRIVERS:
        yield from driver.list()


class UnsupportedDeviceError(Exception):
    pass
