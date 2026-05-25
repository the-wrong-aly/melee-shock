from abc import abstractmethod, ABC
from melee_shock.models import Player, OutputMode
import logging

logger = logging.getLogger(__name__)


class BaseAPI(ABC):
    def __init__(self, players: dict[int, Player]):
        self.players = players

    def _map_shockers(self):
        self.shocker_map: dict[int, int] = {}
        num_players = len(self.players)
        if num_players > len(self.shocker_ids):
            raise RuntimeError(
                f"Not enough shockers for players: {num_players} players but only {len(self.shocker_ids)} shockers found"
            )
        shocker_idx = 0
        for port in self.players.keys():
            self.shocker_map[port] = self.shocker_ids[shocker_idx]
            shocker_idx += 1
        logger.info(f"Mapped shockers to ports: {self.shocker_map}")
        logger.info(f"Unused shockers: {self.shocker_ids[shocker_idx:]}")

    @abstractmethod
    def beep(self, port: int, duration: int):
        pass

    @abstractmethod
    def vibrate(self, port: int, intensity: int, duration: int):
        pass

    @abstractmethod
    def shock(self, port: int, intensity: int, duration: int):
        pass
