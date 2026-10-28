import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, fields
from time import sleep
from typing import Any

import serial
from serial.tools import list_ports

from pokestick import SignalReceived
from pokestick.device import Config, DeviceId
from pokestick.drivers.abc import Watchdog

VID, PID = 0x0483, 0xA26D
CONFIG_SECTION = "watchdog_pro2"

logger = logging.getLogger(__name__)


class WatchdogPro2(Watchdog):
    @classmethod
    def list(cls) -> Iterator[DeviceId]:
        for port in list_ports.comports():
            if port.vid == VID and port.pid == PID:
                yield DeviceId.from_serial(port)

    @classmethod
    def is_compatible(cls, device: DeviceId) -> bool:
        return device.vid == VID and device.pid == PID

    def __init__(self, device: DeviceId):
        self._device_id = device
        self.port = serial.Serial(str(device.device), baudrate=9600, timeout=2)

    def device_id(self) -> DeviceId:
        return self._device_id

    def read_config(self) -> Config:
        with self.port as port:
            hw_config = read_config(port)
            config = {CONFIG_SECTION: asdict(hw_config)}
        return config

    def update_config(self, config: Config):
        with self.port as port:
            hw_config = read_config(port)
            hw_config.update(config)
            write_config(port, hw_config)

    def serve(self):
        logger.info("Starting server for %s", self.device_id())
        with unpause_context(self.port) as port:
            hw_config = read_config(port)
            ping_interval = max(
                hw_config.heartbeat_timeout * 60 / 10,
                min(hw_config.heartbeat_timeout * 60 / 2, 5),
            )
            logger.debug("Ping interval is %s", ping_interval)
            while True:
                request = b"~U"
                response = send_request(port, request)
                assert response.rstrip() in (b"Alert", b"~A")
                try:
                    sleep(ping_interval)
                except (KeyboardInterrupt, SignalReceived) as exc:
                    if isinstance(exc, SignalReceived):
                        logger.info("%s received, exiting...", exc.signal.name)
                    else:
                        logger.info("%s received, exiting...", type(exc).__name__)
                    break

    def reset(self):
        with self.port as port:
            request = b"~T1"
            response = send_request(port, request)
            assert response.rstrip() in (request, b"")

    def power(self):
        with self.port as port:
            request = b"~T3"
            response = send_request(port, request)
            assert response.rstrip() == request

    def power_cycle(self):
        with self.port as port:
            request = b"~T2"
            response = send_request(port, request)
            assert response.rstrip() == request


@contextmanager
def unpause_context(port: serial.Serial):
    with port:
        request = b"~P0"
        response = send_request(port, request)
        assert response.rstrip() in (request, b"Invalid")
        yield port
        request = b"~P1"
        response = send_request(port, request)
        assert response.rstrip() == request


@dataclass
class HwConfig:
    """
    Units:
    heartbeat_timeout: minutes
    reset_impulse: 100 milliseconds
    power_off_impulse: seconds
    power_cycle_interval: seconds
    power_on_impulse: 100 milliseconds
    num_contiguous_resets: count
    """

    heartbeat_timeout: int
    reset_impulse: int
    power_off_impulse: int
    power_cycle_interval: int
    power_on_impulse: int
    num_contiguous_resets: int

    def validate(self):
        for key, value in asdict(self).items():
            if not 0 <= value <= 15:
                raise ValueError(f"{key} must be between 0 and 15, got {value}")

    def update(self, config: dict[Any, Any]):
        values = config.get(CONFIG_SECTION)
        if not values:
            return

        if not isinstance(values, dict):
            raise TypeError(f"Value of config section {CONFIG_SECTION:r} must be a map")

        valid_fields = {f.name for f in fields(self)}

        for key, value in values.items():
            if not isinstance(key, str) or key not in valid_fields:
                raise ValueError(f"Unknown configuration field: {key!r}")

            if type(value) is not int:
                raise TypeError(f"{key} must be an int, got {type(value).__name__}")

            if not 0 <= value <= 15:
                raise ValueError(f"{key} must be between 0 and 15, got {value}")

        for key, value in values.items():
            setattr(self, key, value)


ConfigDigits = tuple[int, ...]


def decode_config_response(data: bytes) -> ConfigDigits:
    if not data.endswith(b"\n"):
        raise TimeoutError(f"Incomplete response: {data!r}")

    data = data.rstrip(b"\n")
    if not data.startswith(b"~F") or len(data) != 13:
        raise ValueError(f"Unexpected response: {data!r}")

    values = data[2:].decode("ascii")
    try:
        digits = tuple(int(c, 16) for c in values)
    except ValueError as exc:
        raise ValueError(f"Invalid configuration response: {data!r}") from exc

    return digits


def encode_config_request(digits: ConfigDigits) -> bytes:
    if len(digits) != 11:
        raise ValueError(
            f"The length of the config tuple should be 11, given tuple has {len(digits)} items"
        )
    if not all(0 <= x < 16 for x in digits):
        raise ValueError(f"All values must be in between 0 and 15, {digits:r} is given")

    command = "~W" + "".join(f"{x:X}" for x in digits)

    return command.encode("ascii")


def send_request(port: serial.Serial, request: bytes) -> bytes:
    logger.debug("> %s", request)
    port.reset_input_buffer()
    port.write(request)
    port.flush()
    response = port.read_until(b"\n")
    logger.debug("< %s", response.rstrip())
    return response


def read_config(port: serial.Serial) -> HwConfig:
    """Read the configuration stored in the watchdog."""
    response = send_request(port, b"~F")
    digits = decode_config_response(response)
    return HwConfig(
        heartbeat_timeout=digits[0],
        reset_impulse=digits[1],
        power_off_impulse=digits[2],
        power_cycle_interval=digits[3],
        power_on_impulse=digits[4],
        num_contiguous_resets=digits[7],
    )


def write_config(port: serial.Serial, hw_config: HwConfig):
    """Write configuration to the watchdog."""

    response_pre = send_request(port, b"~F")
    digits = decode_config_response(response_pre)

    updated = [*digits]

    updated[0] = hw_config.heartbeat_timeout
    updated[1] = hw_config.reset_impulse
    updated[2] = hw_config.power_off_impulse
    updated[3] = hw_config.power_cycle_interval
    updated[4] = hw_config.power_on_impulse
    updated[7] = hw_config.num_contiguous_resets
    updated = tuple(updated)

    if updated == digits:
        return

    request = encode_config_request(updated)
    response_after = send_request(port, request)

    assert request[2:] == response_after[2:].rstrip()
