from abc import abstractmethod, ABC
from dataclasses import dataclass
from melee import GameState


@dataclass
class ShockEvent:
    duration: int
    intensity: int


class BaseMode(ABC):
    def __init__(self):
        self._new_game()

    @abstractmethod
    def _new_game(self):
        pass

    @abstractmethod
    def update(self, gamestate: GameState) -> ShockEvent | None:
        pass
