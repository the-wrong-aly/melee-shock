from abc import abstractmethod, ABC


class BaseSource(ABC):
    @abstractmethod
    def get_state(self):
        pass
