from melee import GameState
from pydantic import BaseModel

from melee_shock.modes.registry import register_mode

from .base import BaseMode, ShockEvent

# roy fully charged fsmash
MAX_DAMAGE_MOVE = 50


@register_mode("damage")
class DamageMode(BaseMode):
    """
    Mode that shocks when a player takes damage.
    """

    class Config(BaseModel):
        name: str = "damage"
        max_intensity: int
        min_duration: float = 0

    def __init__(self, cfg: Config):
        super().__init__()

        self.cfg = cfg

    def _new_game(self):
        self._current_percent = None

    def update(self, port: int, gamestate: GameState) -> ShockEvent | None:
        player_state = gamestate.players[port]
        if not player_state:
            return None

        percent = player_state.percent
        if self._current_percent is not None and percent > self._current_percent:
            # player was hit
            intensity = max(
                1,
                min(
                    int(
                        (percent - self._current_percent)
                        / MAX_DAMAGE_MOVE
                        * self.cfg.max_intensity
                    ),
                    self.cfg.max_intensity,
                ),
            )
            duration = max(
                int(self.cfg.min_duration * 1000),
                player_state.hitstun_frames_left * 1000 // 60,
            )
            self._current_percent = percent
            return ShockEvent(duration=duration, intensity=intensity)

        self._current_percent = percent
        return None
