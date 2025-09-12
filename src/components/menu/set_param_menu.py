from .base_menu import BaseMenu


class SetParamMenu(BaseMenu):
    def __init__(self, manager, param_key: str, min_val: int, max_val: int):
        super().__init__(manager)
        self.param_key = param_key
        self.min_val = min_val
        self.max_val = max_val
        self.current_value = self.manager.settings[param_key]

    def handle_input(self, events: list[dict], blink_interval: float) -> None:
        if self._update_blink(blink_interval, fields_to_blink=True):
            self._render()
        changed = False
        for event in events:
            button, event_type = event["button"], event["type"]
            if button in ["up", "down"] and event_type == "short_press":
                step = (
                    1 if self.current_value < 60 else 60
                )  # Dynamique: 1s <60, 60s >=60
                delta = step if button == "up" else -step
                self.current_value = max(
                    self.min_val, min(self.current_value + delta, self.max_val)
                )
                changed = True
            elif button == "menu" and event_type == "short_press":
                self.manager.settings[self.param_key] = self.current_value
                self.manager.save_params()
                self.manager._switch_to("SettingsMenu")
            elif button == "menu" and event_type == "long_press":
                self.manager._switch_to("SettingsMenu")
        if changed:
            self._render()

    def _render(self) -> None:
        label = f"{self.param_key.replace('_', ' ').title()}:"
        if self.current_value < 60:
            text_str = f"{self.current_value}s"  # Affichage en secondes <60
        else:
            text_str = f"{self.current_value // 60}m"  # Affichage en minutes >=60
        self.display.show_settings(text_str, "value", self.blink_state, label=label)
