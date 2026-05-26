# melee-shock

Real-time haptic feedback for Super Smash Bros. Melee. Monitors live game state from Dolphin emulator and triggers physical feedback on a connected [PiShock](https://pishock.com) hub when in-game events occur. Feedback can be either vibration or electrical.

**Please read the *Online Play* section below if looking to play online.**

## Features

- **Damage mode** - triggers feedback when your character takes damage; intensity scales with damage dealt, duration matches hitstun frames
- **Interval mode** - triggers feedback on a fixed time interval
- **Action mode** - triggers feedback when your character enters a specific action state (e.g. shielding, grabbing)
- **Per-player configuration** - each player slot can have its own mode and output type
- **Output modes** - `vibrate`, `shock`, or `disabled` per player
- **In-game controls** - D-Pad Left kills the shock switch; D-Pad Right sends a ping

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

**`damage`** - Fires on hit; intensity scales with damage dealt, duration matches hitstun.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `max_intensity` | int | — | Maximum intensity (scales with damage) |
| `min_duration` | float | `0.05` | Minimum duration in seconds |

**`interval`** - Fires on a fixed frame interval.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `interval` | float | — | Seconds between shocks |
| `intensity` | int | — | Fixed intensity |
| `duration` | float | — | Duration in seconds |

**`action`** - Fires when your character enters a specific action state.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `action` | str | — | Action state name (e.g. `"SHIELD"`, `"GRAB"`). Must match a [`melee.Action`](https://libmelee.readthedocs.io/en/latest/enums.html) enum value |
| `intensity` | int | — | Fixed intensity |
| `do_while` | bool | `false` | If `true`, shocks continuously while the action is held; if `false`, shocks once on entry |

Each player can override the global mode with a `[mode]` block inside their `[players.N]` entry.

## Usage

```bash
python main.py --config config.toml
```

## Online Play

**Your personal shock settings will always be [players.1] in the config.**

To use melee-shock during online matches, you must enable the following gecko code in Dolphin:

```
# From https://github.com/project-slippi/slippi-ssbm-asm/blob/5dccc0e722ed04b0dd2c3617d47fdb8896232a37/Output/Netplay/GALE01r2.ini#L7085-L7188
$Optional: Extract Menu Info [altf4, Fizzi]
*Extracts menu info. Useful for bots.
C21A4FA4 00000077 #Common/ExtractMenuInfo/SendMenuFrame.asm
7C0802A6 90010004
9421FF5C BE810074
3D008048 81089D30
5508443E 2C080202
4182037C 2C080208
41820374 38610008
3863001F 54630034
3880003E 98830000
B1030001 3C80804A
60840BC0 80840000
2C040000 40820018
3CA00000 60A50000
90A30003 90A30007
48000014 80A4000C
90A30003 80A40010
90A30007 3C80804A
60840BC4 80840000
2C040000 40820018
3CA00000 60A50000
90A3000B 90A3000F
48000014 80A4000C
90A3000B 80A40010
90A3000F 3C80804A
60840BC8 80840000
2C040000 40820018
3CA00000 60A50000
90A30013 90A30017
48000014 80A4000C
90A30013 80A40010
90A30017 3C80804A
60840BCC 80840000
2C040000 40820018
3CA00000 60A50000
90A3001B 90A3001F
48000014 80A4000C
90A3001B 80A40010
90A3001F 3C80804D
60846CF2 88840000
98830023 3C80804D
60846CAD 88840000
98830024 3C80803F
60840E08 88840000
98830025 3C80803F
60840E2C 88840000
98830026 3C80803F
60840E50 88840000
98830027 3C80803F
60840E74 88840000
98830028 3C80803F
60840E0A 88840000
98830029 3C80803F
60840E2E 88840000
9883002A 3C80803F
60840E52 88840000
9883002B 3C80803F
60840E76 88840000
9883002C 3C800000
60840000 9083002D
2C080002 40820064
3C80804A 60840BC0
80840000 38840005
88840000 9883002D
3C80804A 60840BC4
80840000 38840005
88840000 9883002E
3C80804A 60840BC8
80840000 38840005
88840000 9883002F
3C80804A 60840BCC
80840000 38840005
88840000 98830030
3C800000 60840000
90830031 3C800000
60840000 90830035
2C080102 41820010
2C080108 41820008
48000054 3C80804D
60847820 80840000
38840010 80840000
38840028 80840000
38840038 80840000
90830031 3C80804D
60847820 80840000
38840010 80840000
38840028 80840000
3884003C 80840000
90830035 3C808047
60849D60 80840000
90830039 3C80804A
608404F0 88840000
9883003D 3C80804A
608404F3 88840000
9883003E 3C80803F
60840E09 88840000
9883003F 3C80804D
60846CF6 88840000
98830040 3C808048
6084082F 88840000
98830041 3C808048
60840853 88840000
98830042 3C808048
60840877 88840000
98830043 3C808048
6084089B 88840000
98830044 3C80803F
60840E0E 88840000
98830045 3C80803F
60840E32 88840000
98830046 3C80803F
60840E56 88840000
98830047 3C80803F
60840E7A 88840000
98830048 3880004A
38A00001 3D808000
618C55F0 7D8903A6
4E800421 BA810074
800100A8 382100A4
7C0803A6 80790000
60000000 00000000
```

This code enables us to read menu info correctly determine your ingame port.

To enable it: open Dolphin, right-click your Melee ISO, select **Properties → Gecko Codes**, and check the box next to the code. If it isn't listed, click **Show Defaults** and paste the code in manually.

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

## TODO

- [ ] Desktop GUI
- [ ] Wii console support
- [ ] Charge meter mode
- [ ] Better support for online opponents

## Thanks

- **Michael** - testing online play

## License

See [LICENSE](LICENSE).
