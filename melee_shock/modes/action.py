import time

import melee
from melee import GameState
from pydantic import BaseModel

from melee_shock.modes.registry import register_mode

from .base import BaseMode, ShockEvent

DURATION = 100  # ms


@register_mode("action")
class ActionMode(BaseMode):
    """
    Mode that shocks when a specific action is performed. If do_while is True, shocks while the action is being performed.
    """

    class Config(BaseModel):
        name: str = "action"
        intensity: int
        action: str | list[str]
        do_while: bool = False

    def __init__(self, cfg: Config):
        super().__init__()

        self.cfg = cfg
        actions = cfg.action if isinstance(cfg.action, list) else [cfg.action]
        self._actions = {melee.Action[a] for a in actions}

    def _new_game(self):
        self._current_action = None
        self._last_shock_time: float | None = None

    def update(self, port: int, gamestate: GameState) -> ShockEvent | None:
        player_state = gamestate.players[port]
        if not player_state:
            return None

        action = player_state.action
        if self.cfg.do_while:
            if action in self._actions:
                now = time.monotonic()
                if (
                    self._last_shock_time is None
                    or (now - self._last_shock_time) * 1000 >= DURATION
                ):
                    self._last_shock_time = now
                    return ShockEvent(duration=DURATION, intensity=self.cfg.intensity)
        else:
            if action in self._actions and self._current_action not in self._actions:
                self._current_action = action
                return ShockEvent(duration=DURATION, intensity=self.cfg.intensity)

        self._current_action = action
        return None
