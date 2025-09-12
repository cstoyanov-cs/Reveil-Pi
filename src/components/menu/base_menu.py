import time
from abc import ABC, abstractmethod
from typing import List, Dict
from src.components.display import Display
from src.components.time import Time
from src.components.alarms import Alarms


class BaseMenu(ABC):
    """Classe abstraite pour les menus du réveil."""

    def __init__(self, manager):
        self.manager = manager  # Référence au MenuManager pour accès aux vars partagées et transitions
        self.display: Display = manager.display
        self.time_manager: Time = manager.time_manager
        self.alarm_manager: Alarms = manager.alarm_manager
        self.blink_state: bool = True
        self.last_blink: float = time.time()

    @abstractmethod
    def handle_input(self, events: List[Dict[str, str]], blink_interval: float) -> None:
        """Traite les événements et gère les transitions."""
        pass

    @abstractmethod
    def _render(self) -> None:
        """Affiche l'état du menu."""
        pass

    def _update_blink(
        self, blink_interval: float, fields_to_blink: bool = False
    ) -> bool:
        """Gère le clignotement si applicable."""
        current_time = time.time()
        if fields_to_blink and current_time - self.last_blink >= blink_interval:
            self.blink_state = not self.blink_state
            self.last_blink = current_time
            return True
        return False

