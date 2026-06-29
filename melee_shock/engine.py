import logging
import threading
from enum import Enum

import melee
from melee import GameState
from melee.gamestate import port_detector

from melee_shock.apis.base import BaseAPI
from melee_shock.models import OutputMode, Player
from melee_shock.modes.base import ShockEvent
from melee_shock.sources.base import BaseSource

logger = logging.getLogger(__name__)


KILL_BUTTON = melee.Button.BUTTON_START
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
        global_max_intensity: int | None = None,
    ):
        self.source = source
        self.players = players
        self.api = api
        self.global_max_intensity = global_max_intensity

        self._running = False
        self._thread: threading.Thread | None = None

        self.prev_frame: int | None = None
        self.mode = EngineMode.ON

        self.online = False
        self.online_character: melee.Character | None = None
        self.online_costume: int | None = None
        self.online_port: int | None = None
        self.online_mapping: dict[int, int] | None = None

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
        self.api.close()
        logger.info("Engine stopped")

    def run(self):
        """Run blocking (for CLI use)."""
        self._running = True
        try:
            self._loop()
        finally:
            self.source.stop()
            self.api.close()

    def _loop(self):
        while self._running:
            try:
                state = self.source.get_state()
            except Exception:
                logger.info("Source disconnected, stopping")
                break
            try:
                self._tick(state)
            except Exception:
                logger.exception("Error during engine tick")

    def _tick(self, state: GameState):
        if state.menu_state in [melee.Menu.IN_GAME, melee.Menu.SUDDEN_DEATH]:
            self._game_tick(state)
        elif state.menu_state in [
            melee.Menu.CHARACTER_SELECT,
            melee.Menu.SLIPPI_ONLINE_CSS,
        ]:
            self._menu_tick(state)
        else:
            return

    def _menu_tick(self, state: GameState):
        if state.menu_state == melee.Menu.SLIPPI_ONLINE_CSS and not self.online:
            logger.info("Online CSS detected, setting online mode to True")
            self.online = True
        elif state.menu_state == melee.Menu.CHARACTER_SELECT and self.online:
            logger.info("Character select detected, setting online mode to False")
            self.online = False
            self.online_mapping = None
            self.online_character = None
            self.online_costume = None

        if state.menu_state == melee.Menu.SLIPPI_ONLINE_CSS and self.online:
            # we are always port 1 when in online CSS
            player_state = state.players[1]
            character = player_state.character
            costume = player_state.costume
            if character != self.online_character or costume != self.online_costume:
                self.online_character = character
                self.online_costume = costume
                logger.debug(
                    f"Online character: {self.online_character}, costume: {self.online_costume}"
                )

    def _game_tick(self, state: GameState):
        # new game started
        if self.prev_frame is None or state.frame < self.prev_frame:
            self.mode = EngineMode.ON
            logger.info("New game detected, resetting engine mode to ON")

            for player in self.players.values():
                for player_mode in player.modes:
                    player_mode._new_game()

            if self.online:
                online_port = port_detector(
                    state, self.online_character, self.online_costume
                )
                if online_port == 0:
                    logger.warning("Failed to detect online port, disabling shocks")
                    self.online_mapping = {p: 0 for p in range(1, 5)}
                else:
                    remaining = [p for p in range(1, 5) if p != online_port]
                    self.online_mapping = {
                        1: online_port,
                        **{i + 2: p for i, p in enumerate(remaining)},
                    }
                    logger.debug(f"Online port mapping: {self.online_mapping}")

        if self.mode == EngineMode.ON:
            kill_pressed = any(
                (
                    ps := state.players.get(
                        self.online_mapping[port] if self.online else port
                    )
                )
                is not None
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

        for logical_port, player in self.players.items():
            game_port = (
                self.online_mapping[logical_port] if self.online else logical_port
            )

            player_state = state.players.get(game_port)
            # player_state is None when it is in the config but not in game
            if player_state is None:
                continue

            # ping button is handled for all players, even if their output mode is disabled
            if player_state.controller_state.button[PING_BUTTON]:
                logger.info(f"Ping button pressed, beeping player {logical_port}")
                self.api.beep(logical_port, duration=500)

            if self.mode == EngineMode.ON:
                if player.output_mode == OutputMode.DISABLED:
                    continue

                # last mode that fires an event wins per tick
                event: ShockEvent | None = None
                for player_mode in player.modes:
                    result = player_mode.update(game_port, state)
                    if result is not None:
                        event = result

                if event is None:
                    continue

                try:
                    # final safety clamp on intensity before sending to API
                    intensity = event.intensity
                    if self.global_max_intensity is not None:
                        clamped = min(intensity, self.global_max_intensity)
                        if clamped < intensity:
                            logger.debug(
                                f"Intensity clamped by global_max_intensity: {intensity} -> {clamped}"
                            )
                        intensity = clamped

                    if player.output_mode == OutputMode.VIBRATE:
                        self.api.vibrate(logical_port, intensity, event.duration)
                    elif player.output_mode == OutputMode.SHOCK:
                        self.api.shock(logical_port, intensity, event.duration)
                except Exception:
                    logger.exception("Shock failed for player %d", logical_port)

        self.prev_frame = state.frame
