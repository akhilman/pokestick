import logging
from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Any

from .device_id import DeviceId

logger = logging.getLogger(__name__)

Config = dict[str, dict[str, Any]]


class Watchdog(ABC):
    @classmethod
    @abstractmethod
    def list(cls) -> Iterator[DeviceId]:
        raise NotImplementedError

    @classmethod
    def is_compatible(cls, device: DeviceId) -> bool:
        return False

    @abstractmethod
    def __init__(self, device: DeviceId):
        raise NotImplementedError

    @abstractmethod
    def device_id(self) -> DeviceId:
        raise NotImplementedError

    @abstractmethod
    def read_config(self) -> Config:
        raise NotImplementedError

    @abstractmethod
    def update_config(self, config: Config):
        _ = config
        raise NotImplementedError

    def reset(self):
        logger.warning("Reset does not supported by %s", type(self).__name__)

    def power(self):
        logger.warning("Power off does not supported by %s", type(self).__name__)

    def power_cycle(self):
        logger.warning("Power cycle does not supported by %s", type(self).__name__)

    @abstractmethod
    def serve(self):
        raise NotImplementedError
