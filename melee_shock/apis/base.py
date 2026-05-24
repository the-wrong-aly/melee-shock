from abc import abstractmethod, ABC


class BaseAPI(ABC):
    def __init__(self):
        # TODO: construct player_id -> shocker_id mapping
        ...

    @abstractmethod
    def beep(self, player_id: int, duration: int):
        pass

    @abstractmethod
    def vibrate(self, player_id: int, intensity: int, duration: int):
        pass

    @abstractmethod
    def shock(self, player_id: int, intensity: int, duration: int):
        pass
