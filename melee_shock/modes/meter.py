from pydantic import BaseModel

from melee import GameState
from melee_shock.modes.registry import register_mode
import melee

from .base import BaseMode, ShockEvent

METER_BUTTON = melee.Button.BUTTON_D_DOWN


@register_mode("meter")
class MeterMode(BaseMode):
    """
    Mode that grants you meter charge when you take damage.
    Taunting also grants meter.
    Pressing dpad down will consume meter to shock your opponent.
    """

    class Config(BaseModel):
        name: str = "meter"
        intensity: int = 10
        duration: float = 1  # s
        num_bars: int = 3
        percent_per_bar: int = 100
        taunt_meter: int = 0

    def __init__(self, cfg: Config):
        super().__init__()
        self.cfg = cfg

    @property
    def meter_fraction(self) -> float:
        max_meter = self.cfg.num_bars * self.cfg.percent_per_bar
        return min(self._meter, max_meter) / max_meter if max_meter > 0 else 0.0

    def _new_game(self):
        self._meter = 0
        self._current_percent = None
        self._meter_trigger = False
        self._taunting = False
        self._other_port = None

    def update(self, port: int, gamestate: GameState) -> ShockEvent | None:
        # Any shock event from this mode will go to `port`, so internally track the other player's meter
        players = gamestate.players
        if self._other_port is None:
            if len(players) != 2:
                raise ValueError("Meter mode only supports 2 players")
            self._other_port = next(k for k in players.keys() if k != port)

        other_player_state = players[self._other_port]
        if not other_player_state:
            return None

        # Check if the other player is pressing down on the dpad
        shock_event = None
        if other_player_state.controller_state.button[METER_BUTTON]:
            if not self._meter_trigger and self._meter >= self.cfg.percent_per_bar:
                self._meter_trigger = True
                self._meter -= self.cfg.percent_per_bar
                shock_event = ShockEvent(
                    duration=self.cfg.duration * 1000, intensity=self.cfg.intensity
                )
        else:
            self._meter_trigger = False

        # Update meter based on damage taken
        percent = other_player_state.percent
        if self._current_percent is not None and percent > self._current_percent:
            # player was hit
            damage_taken = percent - self._current_percent
            self._meter += damage_taken
        self._current_percent = percent

        # Update meter based on taunting, taunt has to finish so ensure that we reach the STANDING action
        if other_player_state.action == melee.Action.STANDING and self._taunting:
            self._taunting = False
            self._meter += self.cfg.taunt_meter
        elif other_player_state.action in (
            melee.Action.TAUNT_LEFT,
            melee.Action.TAUNT_RIGHT,
        ):
            self._taunting = True
        else:
            self._taunting = False

        # Cap meter at the maximum number of bars
        self._meter = min(self._meter, self.cfg.num_bars * self.cfg.percent_per_bar)

        return shock_event
