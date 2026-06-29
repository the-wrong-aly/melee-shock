import random

from melee import GameState
from pydantic import BaseModel, model_validator

from .base import BaseMode, ShockEvent
from melee_shock.modes.registry import register_mode


@register_mode("interval")
class IntervalMode(BaseMode):
    """
    Mode that shocks every `interval` seconds.
    """

    class Config(BaseModel):
        name: str = "interval"
        interval: float | None = 5
        interval_min: float | None = None
        interval_max: float | None = None
        intensity: int | None = 10
        intensity_min: int | None = None
        intensity_max: int | None = None
        duration: float = 0.01

        @model_validator(mode="after")
        def check_fields(self):
            has_fixed_interval = self.interval is not None
            has_range_interval = (
                self.interval_min is not None and self.interval_max is not None
            )
            if not has_fixed_interval and not has_range_interval:
                raise ValueError(
                    "provide either 'interval' or both 'interval_min' and 'interval_max'"
                )
            if has_range_interval and self.interval_min > self.interval_max:
                raise ValueError("'interval_min' must be <= 'interval_max'")

            has_fixed_intensity = self.intensity is not None
            has_range_intensity = (
                self.intensity_min is not None and self.intensity_max is not None
            )
            if not has_fixed_intensity and not has_range_intensity:
                raise ValueError(
                    "provide either 'intensity' or both 'intensity_min' and 'intensity_max'"
                )
            if has_range_intensity and self.intensity_min > self.intensity_max:
                raise ValueError("'intensity_min' must be <= 'intensity_max'")

            return self

    def __init__(self, cfg: Config):
        self.cfg = cfg
        super().__init__()

    def _new_game(self):
        self._last_shock_frame = None
        self._next_interval_frames = self._resolve_interval_frames()

    def _resolve_interval_frames(self) -> float:
        if self.cfg.interval_min is not None and self.cfg.interval_max is not None:
            return random.uniform(self.cfg.interval_min, self.cfg.interval_max) * 60
        return self.cfg.interval * 60

    def _resolve_intensity(self) -> int:
        if self.cfg.intensity_min is not None and self.cfg.intensity_max is not None:
            return random.randint(self.cfg.intensity_min, self.cfg.intensity_max)
        return self.cfg.intensity

    def update(self, port: int, gamestate: GameState) -> ShockEvent | None:
        frame = gamestate.frame

        # wait one interval before the initial shock
        if self._last_shock_frame is None:
            self._last_shock_frame = frame
            return None

        if frame - self._last_shock_frame >= self._next_interval_frames:
            self._last_shock_frame = frame
            self._next_interval_frames = self._resolve_interval_frames()
            return ShockEvent(
                duration=int(self.cfg.duration * 1000),
                intensity=self._resolve_intensity(),
            )

        return None
