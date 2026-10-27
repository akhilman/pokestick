from dataclasses import dataclass
from pathlib import Path
from typing import Self

from serial.tools.list_ports_linux import SysFS


@dataclass
class DeviceId:
    device: Path
    vid: int | None
    pid: int | None
    serial: str | None
    description: str

    @classmethod
    def from_serial(cls, port: SysFS) -> Self:
        return cls(
            device=port.device,
            vid=port.vid,
            pid=port.pid,
            serial=port.serial_number,
            description=port.description,
        )

    def matches(self, value: str) -> bool:
        if value in str(self.device):
            return True

        value = value.lower()

        if self.vid and self.pid and value in f"{self.vid:x}:{self.pid:x}":
            return True

        if self.serial and value in self.serial.lower():
            return True

        if value in self.description.lower():  # noqa: SIM103
            return True

        return False
