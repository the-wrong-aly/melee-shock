import logging
import threading
import melee
from enum import Enum

from melee import GameState
from melee_shock.apis.base import BaseAPI
from melee_shock.sources.base import BaseSource
from melee_shock.modes.base import ShockEvent
from melee_shock.models import OutputMode, Player

logger = logging.getLogger(__name__)


KILL_BUTTON = melee.Button.BUTTON_D_LEFT
PING_BUTTON = melee.Button.BUTTON_D_RIGHT


class EngineMode(Enum):
    ON = "on"
    OFF = "off"


class Engine:
    def __init__(
        self,
        source: BaseSource,
        players: dict[int, Player],
        api: BaseAPI,
    ):
        self.source = source
        self.players = players
        self.api = api

        self._running = False
        self._thread: threading.Thread | None = None

        self.prev_frame: int | None = None
        self.mode = EngineMode.ON

    def start(self):
        """Start the engine in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("Engine started")

    def stop(self):
        """Signal the engine to stop and wait for it to finish."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        self.source.stop()
        logger.info("Engine stopped")

    def run(self):
        """Run blocking (for CLI use)."""
        self._running = True
        try:
            self._loop()
        finally:
            self.source.stop()

    def _loop(self):
        while self._running:
            try:
                state = self.source.get_state()
            except Exception:
                logger.info("Source disconnected, stopping")
                break
            if state is None:
                break
            try:
                self._tick(state)
            except Exception:
                logger.exception("Error during engine tick")

    def _tick(self, state: GameState):
        if state.menu_state not in [
            melee.Menu.IN_GAME,
            melee.Menu.SUDDEN_DEATH,
        ]:
            return

        # new game started
        if self.prev_frame is None or state.frame < self.prev_frame:
            self.mode = EngineMode.ON
            logger.info("New game detected, resetting engine mode to ON")

            for player in self.players.values():
                if player.mode is not None:
                    player.mode._new_game()

        if self.mode == EngineMode.ON:
            kill_pressed = any(
                (ps := state.players.get(port)) is not None
                and player.output_mode != OutputMode.DISABLED
                and ps.controller_state.button[KILL_BUTTON]
                for port, player in self.players.items()
            )
            if kill_pressed:
                logger.info("Kill button pressed, setting engine mode to OFF")
                self.mode = EngineMode.OFF
                for port, player in self.players.items():
                    if player.output_mode != OutputMode.DISABLED:
                        self.api.end(port)

        for port, player in self.players.items():
            player_state = state.players.get(port)
            # player_state is None when it is in the config but not in game
            if player_state is None:
                continue

            # ping button is handled for all players, even if their output mode is disabled
            if player_state.controller_state.button[PING_BUTTON]:
                logger.info(f"Ping button pressed, beeping player {port}")
                self.api.beep(port, duration=500)

            if self.mode == EngineMode.ON:
                if player.output_mode == OutputMode.DISABLED:
                    continue

                event: ShockEvent | None = player.mode.update(port, state)

                if event is None:
                    continue

                try:
                    if player.output_mode == OutputMode.VIBRATE:
                        self.api.vibrate(port, event.intensity, event.duration)
                    elif player.output_mode == OutputMode.SHOCK:
                        self.api.shock(port, event.intensity, event.duration)
                except Exception:
                    logger.exception("Shock failed for player %d", port)

        self.prev_frame = state.frame
