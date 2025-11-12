from .base_menu import BaseMenu


class SetTimeMenu(BaseMenu):
    def __init__(self, manager, mode: str):
        super().__init__(manager)
        self.mode = mode  # "hour" ou "minute"

    def handle_input(self, events: list[dict], blink_interval: float) -> None:
        if self._update_blink(blink_interval, fields_to_blink=True):
            self._render()
        for event in events:
            button, event_type = event["button"], event["type"]
            if self.mode == "hour":
                if button == "down" and event_type == "short_press":
                    self.manager.setting_hour = (self.manager.setting_hour + 1) % 24
                elif button == "up" and event_type == "short_press":
                    self.manager.setting_hour = (self.manager.setting_hour - 1) % 24
                elif button == "menu" and event_type == "short_press":
                    self.mode = "minute"
                elif button == "menu" and event_type == "long_press":
                    self.manager.current_menu = None
                    self.manager.time_initialized = False
            elif self.mode == "minute":
                if button == "down" and event_type == "short_press":
                    self.manager.setting_minute = (self.manager.setting_minute + 1) % 60
                elif button == "up" and event_type == "short_press":
                    self.manager.setting_minute = (self.manager.setting_minute - 1) % 60
                elif button == "menu" and event_type == "short_press":
                    self.manager.time_manager.set_time(
                        self.manager.setting_hour, self.manager.setting_minute
                    )
                    self.manager.current_menu = None
                    self.manager.time_initialized = False
                elif button == "menu" and event_type == "long_press":
                    self.manager.current_menu = None
                    self.manager.time_initialized = False
            self._render()

    def _render(self) -> None:
        time_str = f"{self.manager.setting_hour:02d}:{self.manager.setting_minute:02d}"
        blink_field = "hours" if self.mode == "hour" else "minutes"
        self.display.show_settings(time_str, blink_field, self.blink_state)

