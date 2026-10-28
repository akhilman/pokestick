import argparse
import json
import logging
import os
import signal
import sys
import tomllib
from collections.abc import Iterable, Iterator
from pathlib import Path

from . import APP_NAME, ConfigurationError, DeviceNotFoundError, SignalReceived, drivers
from .device import Config, DeviceId

logger = logging.getLogger()


def main():
    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description="A Linux daemon that pings a hardware USB watchdog and lets it physically reboot the PC when the pings stop.",
    )
    parser.add_argument(
        "--config",
        "-c",
        type=readable_file,
        help="specify a configuration file (.toml or .json)",
    )
    parser.add_argument("--debug", action="store_true", help="enable debug output")

    subcommands = parser.add_subparsers(title="command", required=True)

    cmd = subcommands.add_parser("list", help="list connected watchdog devices")
    cmd.set_defaults(func=list_devices)

    cmd = subcommands.add_parser("config", help="dump the current configuration")
    add_device_arg(cmd)
    cmd.set_defaults(func=dump_config)

    cmd = subcommands.add_parser("serve", help="run the watchdog daemon")
    add_device_arg(cmd)
    cmd.set_defaults(func=serve)

    cmd = subcommands.add_parser("reset", help="trigger the reset action")
    add_device_arg(cmd)
    cmd.set_defaults(func=push_reset)

    cmd = subcommands.add_parser("power", help="trigger the power action")
    add_device_arg(cmd)
    cmd.set_defaults(func=push_power)

    cmd = subcommands.add_parser("power-cycle", help="trigger a power cycle")
    add_device_arg(cmd)
    cmd.set_defaults(func=power_cycle)

    args = parser.parse_args()

    config = load_config(args.config)

    logging.basicConfig(
        level=logging.DEBUG
        if args.debug or config.get("main", {}).get("debug", False)
        else logging.INFO,
        # format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

    args.func(config, args)


def add_device_arg(cmd: argparse.ArgumentParser):
    cmd.add_argument(
        "--device",
        "-d",
        help="device to use, will be selected automatically if not specified",
    )


def load_config(config: Path | None) -> Config:
    if not config:
        config_dir = Path("/etc") / APP_NAME
        json_config = config_dir / "config.json"
        toml_config = config_dir / "config.toml"
        if json_config.is_file():
            config = json_config
        elif toml_config.is_file():
            config = toml_config
        else:
            return {}

    if config.suffix == ".json":
        with config.open("rb") as f:
            return json.load(f)

    if config.suffix == ".toml":
        with config.open("rb") as f:
            return tomllib.load(f)

    raise ConfigurationError("Unsupported configuration format, try TOML or JSON")


def deep_update(target: dict, source: dict) -> dict:
    target = {**target}
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            target[key] = deep_update(target[key], value)
        else:
            target[key] = value
    return target


def readable_file(value: str) -> Path:
    path = Path(value)

    if not path.is_file():
        raise argparse.ArgumentTypeError(f"not a regular file: {path}")

    if not os.access(path, os.R_OK):
        raise argparse.ArgumentTypeError(f"file is not readable: {path}")

    return path


def list_devices(_config: Config, _args: argparse.Namespace):
    table = Table()
    table.add_row(
        [
            "DEVICE",
            "VID:PID",
            "SERIAL",
            "DESCRIPTION",
        ]
    )
    for dev in drivers.list_devices():
        vid = hex(dev.vid) if dev.vid else "-"
        pid = hex(dev.pid) if dev.pid else "-"
        serial = dev.serial or "-"
        table.add_row([str(dev.device), f"{vid}:{pid}", serial, dev.description])
    for row in table.format():
        sys.stdout.write(row)
        sys.stdout.write("\n")


def find_device(device: str | None) -> DeviceId:
    device_id = None
    if device:
        for dev in drivers.list_devices():
            if dev.matches(device):
                device_id = dev
                break
    else:
        device_id = next(drivers.list_devices(), None)

    if not device_id:
        raise DeviceNotFoundError(
            "Watchdog device not found" + f": {device}" if device else ""
        )
    return device_id


def dump_config(config: Config, args: argparse.Namespace):
    device_id = find_device(args.device or config.get("main", {}).get("device"))
    watchdog = drivers.create_device(device_id)
    config = deep_update(
        {
            "main": {
                "device": device_id.serial or device_id.device,
                "debug": args.debug,
            },
            **watchdog.read_config(),
        },
        config,
    )
    json.dump(config, sys.stdout, indent=2)
    sys.stdout.write("\n")


def serve(config: Config, args: argparse.Namespace):
    device_id = find_device(args.device or config.get("main", {}).get("device"))
    watchdog = drivers.create_device(device_id)
    watchdog.update_config(config)

    def sigterm_handler(signum, _frame):
        raise SignalReceived(signal.Signals(signum))

    signal.signal(signal.SIGTERM, sigterm_handler)
    watchdog.serve()


def push_reset(config: Config, args: argparse.Namespace):
    device_id = find_device(args.device or config.get("main", {}).get("device"))
    watchdog = drivers.create_device(device_id)
    watchdog.update_config(config)
    watchdog.reset()


def push_power(config: Config, args: argparse.Namespace):
    device_id = find_device(args.device or config.get("main", {}).get("device"))
    watchdog = drivers.create_device(device_id)
    watchdog.update_config(config)
    watchdog.power()


def power_cycle(config: Config, args: argparse.Namespace):
    device_id = find_device(args.device or config.get("main", {}).get("device"))
    watchdog = drivers.create_device(device_id)
    watchdog.update_config(config)
    watchdog.power_cycle()


class Table:
    def __init__(self):
        self.rows: list[list[str]] = []

    def add_row(self, items: Iterable[str]):
        self.rows.append(list(items))

    def format(self) -> Iterator[str]:
        column_widths = []
        for row in self.rows:
            for n, item in enumerate(row):
                if len(column_widths) > n:
                    column_widths[n] = max(column_widths[n], len(item))
                else:
                    column_widths.append(len(item))
        for row in self.rows:
            line_parts = []
            for item, width in zip(row, column_widths):
                line_parts.append(item.ljust(width))
            yield "  ".join(line_parts)
