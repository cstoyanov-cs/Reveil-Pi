from .base_menu import BaseMenu


class SetFrequencyMenu(BaseMenu):
    def __init__(self, manager, alarm_number: int):
        super().__init__(manager)
        self.alarm_number = alarm_number
        self.freq_options = ["T", "S", "WE"]
        self.current_freq = self.manager.alarm_manager.alarm_states[self.alarm_number][
            "frequency"
        ]

    def handle_input(self, events: list[dict], blink_interval: float) -> None:
        if self._update_blink(blink_interval, fields_to_blink=True):
            self._render()
        changed = False
        for event in events:
            button, event_type = event["button"], event["type"]
            if button in ["up", "down"] and event_type == "short_press":
                idx = self.freq_options.index(self.current_freq)
                idx = (idx + (1 if button == "up" else -1)) % len(self.freq_options)
                self.current_freq = self.freq_options[idx]
                changed = True
            elif button == "menu" and event_type == "short_press":
                hour = self.manager.alarm_manager.alarm_states[self.alarm_number][
                    "hour"
                ]
                minute = self.manager.alarm_manager.alarm_states[self.alarm_number][
                    "minute"
                ]
                enabled = self.manager.alarm_manager.alarm_states[self.alarm_number][
                    "enabled"
                ]
                self.manager.alarm_manager.set_alarm(
                    self.alarm_number, hour, minute, enabled, self.current_freq
                )
                self.manager._switch_to("AlarmSubMenu")
                self.manager.selected_option = 2 if self.alarm_number == 1 else 3
            elif button == "menu" and event_type == "long_press":
                self.manager.current_menu = None
                changed = True
        if changed:
            self._render()

    def _render(self) -> None:
        text_str = f"Fréq A{self.alarm_number}: {self.current_freq}"
        self.display.show_settings(
            text_str, "value", self.blink_state, label="Réglage fréquence"
        )
