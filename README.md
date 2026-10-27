# pokestick

A Linux daemon that pings a USB hardware watchdog and allows it to physically reboot the PC when the pings stop.

`pokestick` can discover connected watchdog devices, inspect and update configuration, run the watchdog daemon, and trigger hardware Reset and Power actions.

## Supported watchdog devices

* 0x483:0xa26d USB Watchdog - Open Development

More devices could be added later. See `src/pokestick/drviers` for details.

## Usage

```text
pokestick [--config CONFIG] [--debug] COMMAND
```

### Global options

| Option | Description |
|---|---|
| `-h`, `--help` | Show help and exit |
| `-c`, `--config CONFIG` | Specify a configuration file (`.toml` or `.json`) |
| `--debug` | Enable debug output |

If `--config` is not specified, `pokestick` searches for a configuration file in `/etc/pokestick/`, using the names `config.json` and `config.toml`.

### Commands

| Command | Description |
|---|---|
| `list` | List connected watchdog devices |
| `config` | Dump the current configuration |
| `serve` | Run the watchdog daemon |
| `reset` | Trigger the Reset action |
| `power` | Trigger the Power action |
| `power-cycle` | Trigger a power cycle |

Use `pokestick COMMAND --help` to see the options available for a specific command.

## Device discovery

Run:

```bash
pokestick list
```

Example output:

```text
DEVICE        VID:PID       SERIAL                    DESCRIPTION
/dev/ttyACM0  0x483:0xa26d  313134574E30531500260049  USB Watchdog - Open Development
```

The `--device` (`-d`) option selects which watchdog device to use. It is available for the `serve` and `config` commands.

```bash
pokestick serve --device 313134574E30531500260049
pokestick config --device ttyACM0
```

The selector can match any part of a device's fields except the `DEVICE` path's `/dev/` prefix. Matching against the device path is case-sensitive; matching against the other fields is case-insensitive.

If `--device` is omitted, a device is selected automatically.

## Configuration

Display the current configuration:

```bash
pokestick config
```

Example output:

```json
{
  "main": {
    "device": "313134574E30531500260049",
    "debug": false
  },
  "watchdog_pro2": {
    "heartbeat_timeout": 5,
    "reset_impulse": 2,
    "power_off_impulse": 5,
    "power_cycle_interval": 3,
    "power_on_impulse": 5,
    "num_contiguous_resets": 1
  }
}
```

The configuration can be stored in JSON or TOML format. Use `--config` to specify a particular file:

```bash
pokestick --config /path/to/config.toml config
```

### Configuration sections

#### `main`

| Field | Description |
|---|---|
| `device` | Same as `--device`, could match to any field of `pokestick list` output |
| `debug` | Enable debug output (`true` or `false`) |

#### `watchdog_pro2`

This section configures the USB WatchDog Pro2 hardware.

| Field | Unit | Description |
|---|---|---|
| `heartbeat_timeout` | Minutes | Time without a heartbeat before the watchdog initiates recovery |
| `reset_impulse` | 100 milliseconds | Duration of the Reset output pulse |
| `power_off_impulse` | Seconds | Duration of the Power output pulse used to turn the PC off |
| `power_cycle_interval` | Seconds | Wait interval between the Power-off and Power-on pulses during a power cycle |
| `power_on_impulse` | 100 milliseconds | Duration of the Power output pulse used to turn the PC on |
| `num_contiguous_resets` | Attempts | Maximum number of Reset or Power actions before the watchdog stops automatic recovery; `0` means unlimited |

The hardware parameters are encoded as hexadecimal digits by the device protocol. Their configured values must be between `0` and `15`, inclusive. For `num_contiguous_resets`, `0` has the special meaning of unlimited attempts.

**Note:** `power_off_impulse` and `power_on_impulse` refer to different phases of the power-control sequence. The interval between the two pulses is configured separately by `power_cycle_interval`.

## Running the daemon

Start the watchdog daemon:

```bash
pokestick serve
```

Specify a device explicitly if necessary:

```bash
pokestick serve --device 313134574E30531500260049
```

The daemon periodically sends heartbeats to the watchdog. If the PC stops sending them, the hardware watchdog can initiate recovery independently of the daemon.

## Hardware actions

The following commands request hardware actions:

```bash
pokestick reset
pokestick power
pokestick power-cycle
```

**Warning:** These commands can reset or power off the PC. Use them only when an unexpected interruption is safe.

## License

See the repository for license information.
