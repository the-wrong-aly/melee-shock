from .base import BaseSource
import logging
import melee
from typing import Optional

logger = logging.getLogger(__name__)


class DolphinSource(BaseSource):
    def __init__(
        self,
        dolphin_path: Optional[str] = None,
        iso_path: Optional[str] = None,
        debug=False,
    ):
        if debug:
            self.log = melee.Logger()
        else:
            self.log = None

        self.dolphin_path = dolphin_path
        self.iso_path = iso_path
        self.console = self._make_console()

    def _make_console(self):
        return melee.Console(
            path=self.dolphin_path,
            fullscreen=False,
            logger=self.log,
        )

    def connect(self):
        """Call once at startup before the game loop."""
        if not self.console.connect():
            logger.info("No running Dolphin found, launching...")
            # console in broken state after failed connect, make a new one
            self.console = self._make_console()
            self.console.run(self.iso_path)
            if not self.console.connect():
                raise RuntimeError("Failed to connect to Dolphin")
        logger.info("Console connected")

    def get_state(self):
        gamestate = self.console.step()
        if self.log:
            self.log.logframe(gamestate)
            self.log.writeframe()

        return gamestate

    def stop(self):
        self.console.stop()
        if self.log:
            self.log.writelog()
            logger.info("Log file created: " + self.log.filename)
