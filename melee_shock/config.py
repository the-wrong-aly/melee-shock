import tomllib
from pathlib import Path
from pydantic import BaseModel, field_validator
from melee_shock.modes.registry import get as get_mode


VALID_OUTPUT_MODES = ("shock", "vibrate", "disabled")


class PlayerConfig(BaseModel):
    output_mode: str
    mode: object | None = None

    model_config = {"arbitrary_types_allowed": True}

    @field_validator("output_mode")
    @classmethod
    def valid_output_mode(cls, v):
        if v not in VALID_OUTPUT_MODES:
            raise ValueError(
                f"output_mode must be one of {VALID_OUTPUT_MODES}, got {v!r}"
            )
        return v


class Config(BaseModel):
    dolphin_path: Path | None = None
    iso_path: Path | None = None
    debug: bool
    global_max_intensity: int | None = None
    players: dict[int, PlayerConfig]

    model_config = {"arbitrary_types_allowed": True}


def _resolve_mode(mode_raw: dict) -> object:
    name = mode_raw.get("name")
    if not name:
        raise ValueError("Mode config must have a 'name' field")
    _, mode_config_cls = get_mode(name)
    return mode_config_cls.model_validate(mode_raw)


def load(path: Path = Path("config.toml")) -> Config:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, "rb") as f:
        try:
            raw = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise ValueError(f"Invalid TOML in {path}: {e}") from e

    default_mode_raw = raw.get("mode")

    players = {}
    for port, p in raw.get("players", {}).items():
        try:
            output_mode = p["output_mode"]
            if output_mode == "disabled":
                mode = None
            else:
                mode_raw = p.get("mode") or default_mode_raw
                if mode_raw is None:
                    raise ValueError(
                        f"[players.{port}] has no mode and no global [mode] default is set"
                    )
                mode = _resolve_mode(mode_raw)
            players[int(port)] = PlayerConfig(
                output_mode=output_mode,
                mode=mode,
            )
        except (KeyError, ValueError) as e:
            raise ValueError(f"[players.{port}] {e}") from e

    if not players:
        raise ValueError("At least one player must be defined under [players]")

    return Config(
        dolphin_path=Path(raw["dolphin"]["path"]) if "path" in raw["dolphin"] else None,
        iso_path=Path(raw["dolphin"]["iso"]) if "iso" in raw["dolphin"] else None,
        debug=raw["dolphin"].get("debug", False),
        global_max_intensity=raw.get("global_max_intensity"),
        players=players,
    )
