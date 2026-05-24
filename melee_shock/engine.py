import logging
import threading
from dataclasses import dataclass
from enum import Enum
import melee

from melee import GameState
from melee_shock.modes.base import BaseMode
from melee_shock.apis.base import BaseAPI
from melee_shock.sources.base import BaseSource
from melee_shock.modes.base import ShockEvent

logger = logging.getLogger(__name__)


class OutputMode(Enum):
    DISABLED = "disabled"
    VIBRATE = "vibrate"
    SHOCK = "shock"


@dataclass
class Player:
    output_mode: OutputMode
    mode: BaseMode | None


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
        logger.info(state.menu_state)
        if state.menu_state not in [
            melee.Menu.IN_GAME,
            melee.Menu.SUDDEN_DEATH,
            melee.Menu.CHARACTER_SELECT,
        ]:
            return

        for player_id, player in self.players.items():
            if state.menu_state == melee.Menu.CHARACTER_SELECT:
                player_state = state.players.get(player_id)
                if not player_state:
                    continue

            if player.output_mode == OutputMode.DISABLED:
                continue

            event: ShockEvent | None = player.mode.update(player_id, state)

            if event is None:
                continue

            try:
                if player.output_mode == OutputMode.VIBRATE:
                    self.api.vibrate(player_id, event.intensity, event.duration)
                elif player.output_mode == OutputMode.SHOCK:
                    self.api.shock(player_id, event.intensity, event.duration)
            except Exception:
                logger.exception("Shock failed for player %d", player_id)
