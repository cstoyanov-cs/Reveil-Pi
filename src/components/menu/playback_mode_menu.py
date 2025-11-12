from .base_menu import BaseMenu


class PlaybackModeMenu(BaseMenu):
    def __init__(self, manager):
        super().__init__(manager)
        self.options = ["Mode : ", "Retour"]
        self.manager.selected_option = 0

    def handle_input(self, events: list[dict], blink_interval: float) -> None:
        self._update_blink(blink_interval)
        changed = False
        for event in events:
            button, event_type = event["button"], event["type"]
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
                if self.manager.selected_option == 0:  # Toggle mode
                    current = self.manager.settings["playback_mode"]
                    new_mode = "aleatoire" if current == "sequentiel" else "sequentiel"
                    self.manager.settings["playback_mode"] = new_mode
                    self.manager.save_params()
                    changed = True
                elif self.manager.selected_option == 1:  # Retour
                    self.manager._switch_to("SettingsMenu")
        if changed:
            self._render()

    def _render(self) -> None:
        mode_str = (
            "Séquentiel"
            if self.manager.settings["playback_mode"] == "sequentiel"
            else "Aléatoire"
        )
        opts_with_values = [f"Mode: {mode_str}", "Retour"]
        self.display.show_menu(opts_with_values, self.manager.selected_option)
