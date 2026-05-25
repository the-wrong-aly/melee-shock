from melee import GameState
from pydantic import BaseModel

from .base import BaseMode, ShockEvent
from melee_shock.modes.registry import register_mode


@register_mode("interval")
class IntervalMode(BaseMode):
    """
    Mode that shocks every `interval` seconds.
    """

    class Config(BaseModel):
        name: str = "interval"
        interval: float
        intensity: int
        duration: float

    def __init__(self, cfg: Config):
        super().__init__()

        self.cfg = cfg
        self._interval_frames = cfg.interval * 60

    def _new_game(self):
        self._last_shock_frame = None

    def update(self, port: int, gamestate: GameState) -> ShockEvent | None:
        frame = gamestate.frame

        # wait `_interval_frames` frames before initial shock
        if self._last_shock_frame is None:
            self._last_shock_frame = frame
            return None

        if frame - self._last_shock_frame >= self._interval_frames:
            self._last_shock_frame = frame
            return ShockEvent(duration=int(self.cfg.duration * 1000), intensity=self.cfg.intensity)

        return None
