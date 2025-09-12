from .base_menu import BaseMenu


class MainMenu(BaseMenu):
    def __init__(self, manager):
        super().__init__(manager)
        self.options = [
            "Réglage heure",
            "Réglage alarme",
            "Réglage date",
            "Lire la musique",  # Placé juste avant "Paramètres" comme demandé
            "Paramètres",
            "Basculer DST",
            "Quitter",
        ]
        self.manager.selected_option = 0

    def handle_input(self, events: list[dict], blink_interval: float) -> None:
        self._update_blink(blink_interval)  # Pas de blink ici, mais stub
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
                if self.manager.selected_option == 0:
                    if not self.manager.time_initialized:
                        hours, minutes = map(
                            int, self.manager.time_manager.get_time().split(":")
                        )
                        self.manager.setting_hour, self.manager.setting_minute = (
                            hours,
                            minutes,
                        )
                        self.manager.time_initialized = True
                    self.manager._switch_to("SetTimeMenu", mode="hour")
                elif self.manager.selected_option == 1:
                    self.manager._switch_to("AlarmSubMenu")
                elif self.manager.selected_option == 2:
                    if not self.manager.date_initialized:
                        year, month, date, dow = (
                            self.manager.alarm_manager.rtc.read_date()
                        )
                        self.manager.setting_year = year
                        self.manager.setting_month = month
                        self.manager.setting_date = date
                        self.manager.setting_dow = dow
                        self.manager.date_initialized = True
                    self.manager._switch_to("SetDateMenu", mode="view")
                elif (
                    self.manager.selected_option == 3
                ):  # Handler pour "Lire la musique"
                    self.manager._switch_to("MusicSourceMenu")
                elif (
                    self.manager.selected_option == 4
                ):  # Handler pour "Paramètres" (décalé)
                    self.manager._switch_to("SettingsMenu")
                elif (
                    self.manager.selected_option == 5
                ):  # Handler pour "Basculer DST" (décalé)
                    self.manager.time_manager.toggle_dst()
                    self.manager.current_menu = None
                    changed = True  # Render pour retour à normal
                elif (
                    self.manager.selected_option == 6
                ):  # Handler pour "Quitter" (décalé)
                    self.manager.current_menu = None
                    changed = True  # Render pour retour à normal
        if changed:
            self._render()

    def _render(self) -> None:
        self.display.show_menu(self.options, self.manager.selected_option)
