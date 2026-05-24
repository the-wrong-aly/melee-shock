from abc import abstractmethod, ABC
from dataclasses import dataclass
from melee import GameState


@dataclass
class ShockEvent:
    duration: int
    intensity: int


class BaseMode(ABC):
    @abstractmethod
    def update(self, gamestate: GameState) -> ShockEvent | None:
        pass
