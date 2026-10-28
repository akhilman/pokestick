import signal
from dataclasses import dataclass

APP_NAME = "pokestick"


class DeviceNotFoundError(Exception):
    pass


class ConfigurationError(Exception):
    pass


@dataclass
class SignalReceived(Exception):
    signal: signal.Signals

    def __str__(self) -> str:
        return f"{self.signal} received"
