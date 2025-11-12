from .base_menu import BaseMenu


class SetAlarmMenu(BaseMenu):
    def __init__(self, manager, alarm_number: int, mode: str):
        super().__init__(manager)
        self.alarm_number = alarm_number
        self.mode = mode  # "hour" ou "minute"
        self.last_render_time = 0

    def handle_input(self, events: list[dict], blink_interval: float) -> None:
        if self._update_blink(blink_interval, fields_to_blink=True):
            self._render()
        changed = False
        for event in events:
            button, event_type = event["button"], event["type"]
            if self.mode == "hour":
                if button == "down" and event_type == "short_press":
                    if self.alarm_number == 1:
                        self.manager.alarm1_hour = (self.manager.alarm1_hour + 1) % 24
                    else:
                        self.manager.alarm2_hour = (self.manager.alarm2_hour + 1) % 24
                    changed = True
                elif button == "up" and event_type == "short_press":
                    if self.alarm_number == 1:
                        self.manager.alarm1_hour = (self.manager.alarm1_hour - 1) % 24
                    else:
                        self.manager.alarm2_hour = (self.manager.alarm2_hour - 1) % 24
                    changed = True
                elif button == "menu" and event_type == "short_press":
                    self.mode = "minute"
                    changed = True
                elif button == "menu" and event_type == "long_press":
                    self.manager.current_menu = None
                    changed = True
            elif self.mode == "minute":
                if button == "down" and event_type == "short_press":
                    if self.alarm_number == 1:
                        self.manager.alarm1_minute = (
                            self.manager.alarm1_minute + 1
                        ) % 60
                    else:
                        self.manager.alarm2_minute = (
                            self.manager.alarm2_minute + 1
                        ) % 60
                    changed = True
                elif button == "up" and event_type == "short_press":
                    if self.alarm_number == 1:
                        self.manager.alarm1_minute = (
                            self.manager.alarm1_minute - 1
                        ) % 60
                    else:
                        self.manager.alarm2_minute = (
                            self.manager.alarm2_minute - 1
                        ) % 60
                    changed = True
                elif button == "menu" and event_type == "short_press":
                    hour = (
                        self.manager.alarm1_hour
                        if self.alarm_number == 1
                        else self.manager.alarm2_hour
                    )
                    minute = (
                        self.manager.alarm1_minute
                        if self.alarm_number == 1
                        else self.manager.alarm2_minute
                    )
                    # Garde l'état actuel de enabled (du switch), ne force pas True
                    enabled = self.alarm_manager.alarm_states[self.alarm_number][
                        "enabled"
                    ]
                    self.alarm_manager.set_alarm(
                        self.alarm_number,
                        hour,
                        minute,
                        enabled,
                        self.manager.alarm_manager.alarm_states[self.alarm_number][
                            "frequency"
                        ],  # Garde freq actuelle
                    )
                    self.manager.current_menu = None
                    changed = True
                elif button == "menu" and event_type == "long_press":
                    self.manager.current_menu = None
                    changed = True

        if changed and self._should_render():
            self._render()

        if changed:
            self._render()

    def _render(self) -> None:
        hour = (
            self.manager.alarm1_hour
            if self.alarm_number == 1
            else self.manager.alarm2_hour
        )
        minute = (
            self.manager.alarm1_minute
            if self.alarm_number == 1
            else self.manager.alarm2_minute
        )
        time_str = f"{hour:02d}:{minute:02d}"
        blink_field = "hours" if self.mode == "hour" else "minutes"
        label = f"Réglage {'première' if self.alarm_number == 1 else 'seconde'} alarme"
        self.display.show_settings(time_str, blink_field, self.blink_state, label=label)
