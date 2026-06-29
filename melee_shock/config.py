import tomllib
from pathlib import Path
from pydantic import BaseModel, field_validator
from melee_shock.modes.registry import get as get_mode


VALID_OUTPUT_MODES = ("shock", "vibrate", "disabled")
VALID_SOURCES = ("dolphin", "wii")


class PlayerConfig(BaseModel):
    output_mode: str
    modes: list[object] = []

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
    source: str = "dolphin"
    # dolphin-specific
    dolphin_path: Path | None = None
    iso_path: Path | None = None
    # wii-specific
    wii_ip: str | None = None
    wii_port: int = 51441
    debug: bool = False
    global_max_intensity: int | None = None
    players: dict[int, PlayerConfig]

    model_config = {"arbitrary_types_allowed": True}

    @field_validator("source")
    @classmethod
    def valid_source(cls, v):
        if v not in VALID_SOURCES:
            raise ValueError(f"source.type must be one of {VALID_SOURCES}, got {v!r}")
        return v


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

    default_modes_raw = raw.get("modes", [])

    players = {}
    for port, p in raw.get("players", {}).items():
        try:
            output_mode = p["output_mode"]
            if output_mode == "disabled":
                modes = []
            else:
                modes_raw = p.get("modes") or None
                if not modes_raw:
                    if not default_modes_raw:
                        raise ValueError(
                            f"[players.{port}] has no mode and no global [[modes]] default is set"
                        )
                    modes_raw = default_modes_raw
                modes = [_resolve_mode(m) for m in modes_raw]
            players[int(port)] = PlayerConfig(
                output_mode=output_mode,
                modes=modes,
            )
        except (KeyError, ValueError) as e:
            raise ValueError(f"[players.{port}] {e}") from e

    if not players:
        raise ValueError("At least one player must be defined under [players]")

    src = raw.get("source", {})
    source_type = src.get("type", "dolphin")

    return Config(
        source=source_type,
        dolphin_path=Path(src["path"]) if "path" in src else None,
        iso_path=Path(src["iso"]) if "iso" in src else None,
        wii_ip=src.get("ip"),
        wii_port=src.get("port", 51441),
        debug=src.get("debug", False),
        global_max_intensity=raw.get("global_max_intensity"),
        players=players,
    )
