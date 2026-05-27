# melee-shock

*Hi! Is the pain of playing melee not enough for you? Do you need more motivation to play better? Have you ever wanted to feel like Ash and his greninja from the Pokemon anime? Well this is for you!*

Real-time haptic feedback for Super Smash Bros. Melee. Monitors live game state from Dolphin and triggers physical feedback on a connected [PiShock](https://pishock.com) hub when in-game events occur. Feedback can be either vibration or electric.

**Please read the *Online Play* section below if looking to play online.**

## Safety

- Always follow [PiShock's safety guidelines](https://pishock.com). Do not use around the neck, spine, or chest. Do not use with any heart conditions.
- `melee-shock` is not responsible for any harm caused by misuse of the PiShock device
- Set max intensity to a conservative value before your first session
- The in-game kill switch (D-Pad Left) immediately stops output

## Features

- **Damage mode** - triggers feedback when your character takes damage; intensity scales with damage dealt, duration matches hitstun frames
- **Interval mode** - triggers feedback on a fixed time interval
- **Action mode** - triggers feedback when your character enters a specific action state (e.g. shielding, grabbing)
- **Per-player configuration** - each player slot can have its own mode and output type
- **Output modes** - `vibrate`, `shock`, or `disabled` per player
- **In-game controls** - D-Pad Left kills the shock switch; D-Pad Right sends a ping

## Requirements

- [Slippi Dolphin](https://slippi.gg/) with a Melee ISO
- A PiShock hub connected via USB

## Download

Pre-built Windows executables are available on the [Releases](../../releases) page. Download the latest zip, extract it, and run `melee-shock.exe`.

## Usage

On first launch, configure your setup in the **Settings** tab:

- **Dolphin** - path to your Slippi installation and Melee ISO
- **Global** - set a max intensity (start low) and a default mode with its parameters
- **P1–P4** - set each player's output type (`shock`, `vibrate`, or `disabled`); optionally override the mode per player
- **Shockers** - appears after connecting; use the Beep / Vibrate / Shock buttons to test each shocker

Hit **Save** to write your settings to a config file, then **Connect & Start**. melee-shock will connect to a running Dolphin or launch it automatically.

All settings are locked while running. Hit **Stop** to end the session.

## Modes

**`damage`** - Fires on hit. Intensity scales with the damage dealt; duration matches hitstun.

| Parameter | Description |
|---|---|
| Max intensity | Upper bound on intensity (actual value scales with damage) |
| Min duration | Minimum shock duration in seconds |

**`interval`** - Fires on a fixed timer, regardless of what's happening in game.

| Parameter | Description |
|---|---|
| Interval | Seconds between shocks |
| Intensity | Fixed intensity (0-100) |
| Duration | Shock duration in seconds |

**`action`** - Fires when your character enters a specific action state.

| Parameter | Description |
|---|---|
| Action(s) | Action state name(s) from [`melee.Action`](https://libmelee.readthedocs.io/en/latest/enums.html) (e.g. `SHIELD`, `GRAB`) - comma-separated in the GUI |
| Intensity | Fixed intensity (0-100) |
| Repeat while held | If enabled, shocks continuously while the action is active; otherwise shocks once on entry |

## Online Play

**Your online personal shock settings will always be P1.**

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

This code lets melee-shock correctly determine your in-game port during online matches.

To enable it: open Dolphin, right-click your Melee ISO, select **Properties → Gecko Codes**, and check the box next to the code. If it isn't listed, click **Show Defaults** and paste the code in manually.

## Advanced

<details>
<summary>Config file reference</summary>

The GUI saves settings to a `.toml` file which can also be edited directly.

```toml
global_max_intensity = 10

[dolphin]
path = "path/to/Slippi"
iso = "path/to/melee.iso"
debug = false

[mode]
name = "damage"
max_intensity = 50
min_duration = 0.05

[players.1]
output_mode = "shock"

[players.2]
output_mode = "vibrate"

[players.2.mode]
name = "interval"
interval = 5.0
intensity = 30
duration = 0.3
```

</details>

<details>
<summary>Running from source</summary>

```bash
uv sync
# or
pip install -e .

python gui.py
# or (CLI)
python main.py --config config.toml
```

</details>

<details>
<summary>Building an exe</summary>

```bash
pyinstaller --windowed --name melee-shock --icon assets/icon.ico --collect-all customtkinter --collect-all melee gui.py
```

Output in `dist/melee-shock/`.

</details>

## TODO

- [ ] Wii console support
- [ ] Charge meter mode
- [ ] Better support for online opponents

## Thanks

- **Michael** - testing online play

## License

See [LICENSE](LICENSE).
