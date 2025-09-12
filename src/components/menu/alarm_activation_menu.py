from .base_menu import BaseMenu


class AlarmActivationMenu(BaseMenu):
    def __init__(self, manager, alarm_number: int):
        super().__init__(manager)
        self.alarm_number = alarm_number

    def handle_input(self, events: list[dict], blink_interval: float) -> None:
        self._update_blink(blink_interval)  # Pas de blink, mais stub
        changed = False
        for event in events:
            button, event_type = event["button"], event["type"]
            if button in ["up", "down"] and event_type == "short_press":
                if self.alarm_number == 1:
                    self.manager.alarm1_enabled = not self.manager.alarm1_enabled
                    self.alarm_manager.set_alarm(
                        1,
                        self.manager.alarm1_hour,
                        self.manager.alarm1_minute,
                        self.manager.alarm1_enabled,
                        self.manager.alarm_manager.alarm_states[1]["frequency"],
                    )
                else:
                    self.manager.alarm2_enabled = not self.manager.alarm2_enabled
                    self.alarm_manager.set_alarm(
                        2,
                        self.manager.alarm2_hour,
                        self.manager.alarm2_minute,
                        self.manager.alarm2_enabled,
                        self.manager.alarm_manager.alarm_states[2]["frequency"],
                    )
                changed = True
            elif button == "menu" and event_type == "short_press":
                self.manager._switch_to("AlarmSubMenu")
                self.manager.selected_option = 2 if self.alarm_number == 1 else 3
            elif button == "menu" and event_type == "long_press":
                self.manager.current_menu = None
                changed = True
        if changed:
            self._render()

    def _render(self) -> None:
        enabled = self.manager.alarm_manager.alarm_states[self.alarm_number]["enabled"]
        state = "Activée" if enabled else "Désactivée"
        self.display.show_settings(f"Alarme {self.alarm_number}: {state}", None, True)
