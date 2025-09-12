from .base_menu import BaseMenu


class AlarmSubMenu(BaseMenu):
    def __init__(self, manager):
        super().__init__(manager)
        self.options = [
            "Alarme 1",
            "Alarme 2",
            "Retour",  # Quitter renommé pour cohérence
        ]
        self.manager.selected_option = 0

    def handle_input(self, events: list[dict], blink_interval: float) -> None:
        self._update_blink(blink_interval)  # Pas de blink
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
                if self.manager.selected_option == 0:  # Alarme 1
                    self.manager._switch_to("AlarmConfigMenu", alarm_number=1)
                elif self.manager.selected_option == 1:  # Alarme 2
                    self.manager._switch_to("AlarmConfigMenu", alarm_number=2)
                elif self.manager.selected_option == 2:  # Retour
                    self.manager._switch_to("MainMenu")
                    self.manager.selected_option = (
                        1  # Retour à "Réglage alarme" position
                    )
        if changed:
            self._render()

    def _render(self) -> None:
        self.display.show_menu(self.options, self.manager.selected_option)
