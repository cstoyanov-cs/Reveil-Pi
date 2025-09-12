import time
from .base_menu import BaseMenu


class AlarmConfigMenu(BaseMenu):
    def __init__(self, manager, alarm_number):
        super().__init__(manager)
        self.alarm_number = alarm_number
        self.options = [
            "Régler l'alarme",
            "Régler la fréquence",
            "Régler mode réveil",
            "Retour",
        ]
        self.manager.selected_option = 0
        self.last_render_time = 0

    def handle_input(self, events: list[dict], blink_interval: float) -> None:
        self._update_blink(blink_interval)
        changed = False
        for event in events:
            button = event["button"]
            event_type = event["type"]
            if button == "up" and event_type == "short_press":
                self.manager.selected_option = (self.manager.selected_option - 1) % len(
                    self.options
                )
                changed = True
            elif button == "down" and event_type == "short_press":
                self.manager.selected_option = (self.manager.selected_option + 1) % len(
                    self.options
                )
                changed = True
            elif button == "menu" and event_type == "short_press":
                if self.manager.selected_option == 0:
                    self.manager._switch_to(
                        "SetAlarmMenu", alarm_number=self.alarm_number, mode="hour"
                    )
                elif self.manager.selected_option == 1:
                    self.manager._switch_to(
                        "SetFrequencyMenu", alarm_number=self.alarm_number
                    )
                elif self.manager.selected_option == 2:
                    self.manager._switch_to(
                        "SetAlarmModeMenu", alarm_number=self.alarm_number
                    )
                elif self.manager.selected_option == 3:
                    self.manager._switch_to("AlarmSubMenu")
        current_time = time.time()  # Import time en haut si absent
        if (
            changed and current_time - self.last_render_time >= 0.1
        ):  # Debounce + limite 1 render
            self.last_render_time = current_time
            self._render()  # Seulement si changed et temps écoulé

    def _render(self) -> None:
        self.display.show_menu(self.options, self.manager.selected_option)
