# melee-shock

Real-time haptic feedback for Super Smash Bros. Melee. Monitors live game state from Dolphin emulator and triggers physical feedback on a connected [PiShock](https://pishock.com) hub when in-game events occur. Feedback can be either vibration or electrical.

## Features

- **Damage mode** — triggers feedback when your character takes damage; intensity scales with damage dealt, duration matches hitstun frames
- **Interval mode** — triggers feedback on a fixed time interval
- **Per-player configuration** — each player slot can have its own mode and output type
- **Output modes** — `vibrate`, `shock`, or `disabled` per player
- **In-game controls** — D-Pad Left kills the shock switch; D-Pad Right sends a ping

## Requirements

- Python 3.11+
- [Dolphin emulator](https://dolphin-emu.org) with a Melee ISO
- A PiShock hub connected via USB serial

## Installation

```bash
pip install -e .
```

## Configuration

Copy `config.toml` and edit it for your setup:

```toml
global_max_intensity = 10

[dolphin]
path = "path/to/Slippi"
iso = "path/to/meleeiso"

[mode]
type = "damage"
max_intensity = 1

[[players]]
port = 1
output_mode = "shock"

[[players]]
port = 2
output_mode = "vibrate"
```

**Top-level parameters:**

| Parameter | Description |
|---|---|
| `global_max_intensity` | Hard cap on intensity sent to any output, regardless of mode settings (0–100) |

**Output modes:**

| Value | Effect |
|---|---|
| `shock` | Electrical stimulation |
| `vibrate` | Vibration only |
| `disabled` | No output |

**Built-in modes:**

| Mode | Description |
|---|---|
| `damage` | Fires on hit; intensity/duration scale with damage and hitstun |
| `interval` | Fires every N seconds |

Each player can override the global mode with a `[mode]` block inside their `[[players]]` entry.

## Usage

```bash
python main.py --config config.toml
```

## Project Structure

```
melee_shock/
├── engine.py        # Main event loop
├── config.py        # Config loading
├── models.py        # Shared data models
├── apis/            # Shock hardware backends (PiShock serial)
├── modes/           # Shock trigger logic (damage, interval)
└── sources/         # Game state providers (Dolphin)
```

## License

See [LICENSE](LICENSE).
