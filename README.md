# melee-shock

Real-time haptic feedback for Super Smash Bros. Melee. Monitors live game state from Dolphin emulator and triggers physical feedback on a connected [PiShock](https://pishock.com) hub when in-game events occur. Feedback can be either vibration or electrical.

## Features

- **Damage mode** — triggers feedback when your character takes damage; intensity scales with damage dealt, duration matches hitstun frames
- **Interval mode** — triggers feedback on a fixed time interval
- **Action mode** — triggers feedback when your character enters a specific action state (e.g. shielding, grabbing)
- **Per-player configuration** — each player slot can have its own mode and output type
- **Output modes** — `vibrate`, `shock`, or `disabled` per player
- **In-game controls** — D-Pad Left kills the shock switch; D-Pad Right sends a ping

## Requirements

- Python 3.11+
- [Slippi Dolphin](https://slippi.gg/) with a Melee ISO
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
name      = "damage"
max_intensity = 1

[players.1]
output_mode = "shock"

[players.2]
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

**`damage`** — Fires on hit; intensity scales with damage dealt, duration matches hitstun.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `max_intensity` | int | — | Maximum intensity (scales with damage) |
| `min_duration` | float | `0.05` | Minimum duration in seconds |

**`interval`** — Fires on a fixed frame interval.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `interval` | float | — | Seconds between shocks |
| `intensity` | int | — | Fixed intensity |
| `duration` | float | — | Duration in seconds |

**`action`** — Fires when your character enters a specific action state.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `action` | str | — | Action state name (e.g. `"SHIELD"`, `"GRAB"`) — must match a [`melee.Action`](https://py-slippi.readthedocs.io/en/latest/source/melee.html#melee.enums.Action) enum value |
| `intensity` | int | — | Fixed intensity |
| `do_while` | bool | `false` | If `true`, shocks continuously while the action is held; if `false`, shocks once on entry |

Each player can override the global mode with a `[mode]` block inside their `[players.N]` entry.

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
