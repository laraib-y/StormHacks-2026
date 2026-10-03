from abc import ABC, abstractmethod

from app.schemas.ai import DinnerIntent
from app.schemas.restaurant import RestaurantCandidate


class RestaurantProvider(ABC):
    """Finds a fixed restaurant set for one dinner session."""

    @abstractmethod
    def search(self, intent: DinnerIntent) -> list[RestaurantCandidate]:
        raise NotImplementedError
