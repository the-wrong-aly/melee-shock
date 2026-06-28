from dataclasses import dataclass
from enum import Enum

from melee_shock.modes.base import BaseMode


class OutputMode(Enum):
    DISABLED = "disabled"
    VIBRATE = "vibrate"
    SHOCK = "shock"


@dataclass
class Player:
    output_mode: OutputMode
    modes: list[BaseMode]
