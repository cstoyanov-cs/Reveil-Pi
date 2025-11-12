from .base_menu import BaseMenu


class SetDateMenu(BaseMenu):
    def __init__(self, manager, mode: str):
        super().__init__(manager)
        self.mode = mode  # "view" initial, puis "dow", "date", "month", "year"
        self.dow_map = {
            1: "Dimanche",
            2: "Lundi",
            3: "Mardi",
            4: "Mercredi",
            5: "Jeudi",
            6: "Vendredi",
            7: "Samedi",
        }
        self.selected_option = 0  # Pour mode "view" (0="Régler", 1="Quitter")

    def handle_input(self, events: list[dict], blink_interval: float) -> None:
        if self.mode != "view" and self._update_blink(
            blink_interval, fields_to_blink=True
        ):
            self._render()

        # Reset activity timer sur TOUS les événements
        if events:
            self.manager.reset_activity()

        for event in events:
            button, event_type = event["button"], event["type"]

            if self.mode == "view":
                if button == "down" and event_type == "short_press":
                    self.selected_option = (self.selected_option - 1) % 2
                elif button == "up" and event_type == "short_press":
                    self.selected_option = (self.selected_option + 1) % 2
                elif button == "menu" and event_type == "short_press":
                    if self.selected_option == 0:  # Régler
                        self.mode = "dow"
                    else:  # Quitter
                        self.manager.current_menu = None
                        self.manager.date_initialized = False
                elif button == "menu" and event_type == "long_press":
                    self.manager.current_menu = None
                    self.manager.date_initialized = False

            elif self.mode == "dow":
                if button == "down" and event_type == "short_press":
                    self.manager.setting_dow = (self.manager.setting_dow % 7) + 1
                elif button == "up" and event_type == "short_press":
                    self.manager.setting_dow = ((self.manager.setting_dow - 2) % 7) + 1
                elif button == "menu" and event_type == "short_press":
                    self.mode = "date"
                elif button == "menu" and event_type == "long_press":
                    self.manager.current_menu = None
                    self.manager.date_initialized = False

            elif self.mode == "date":
                if button == "down" and event_type == "short_press":
                    self.manager.setting_date = (self.manager.setting_date % 31) + 1
                elif button == "up" and event_type == "short_press":
                    self.manager.setting_date = (
                        (self.manager.setting_date - 2) % 31
                    ) + 1
                elif button == "menu" and event_type == "short_press":
                    self.mode = "month"
                elif button == "menu" and event_type == "long_press":
                    self.manager.current_menu = None
                    self.manager.date_initialized = False

            elif self.mode == "month":
                if button == "down" and event_type == "short_press":
                    self.manager.setting_month = (self.manager.setting_month % 12) + 1
                elif button == "up" and event_type == "short_press":
                    self.manager.setting_month = (
                        (self.manager.setting_month - 2) % 12
                    ) + 1
                elif button == "menu" and event_type == "short_press":
                    self.mode = "year"
                elif button == "menu" and event_type == "long_press":
                    self.manager.current_menu = None
                    self.manager.date_initialized = False

            elif self.mode == "year":
                if button == "down" and event_type == "short_press":
                    # Incrémente année (limite 2000-2099)
                    self.manager.setting_year += 1
                    if self.manager.setting_year > 2099:
                        self.manager.setting_year = 2000

                elif button == "up" and event_type == "short_press":
                    # Décrémente année (limite 2000-2099)
                    self.manager.setting_year -= 1
                    if self.manager.setting_year < 2000:
                        self.manager.setting_year = 2099

                elif button == "menu" and event_type == "short_press":
                    self.manager.alarm_manager.rtc.set_date(
                        self.manager.setting_year,
                        self.manager.setting_month,
                        self.manager.setting_date,
                        self.manager.setting_dow,
                    )
                    self.manager.current_menu = None
                    self.manager.date_initialized = False

                elif button == "menu" and event_type == "long_press":
                    self.manager.current_menu = None
                    self.manager.date_initialized = False

            self._render()

    def _render(self) -> None:
        """Affiche le jour en haut, la date en dessous, et les options horizontales en bas."""
        day_str = self.dow_map.get(self.manager.setting_dow, "Err")
        date_str = f"{self.manager.setting_date:02d}/{self.manager.setting_month:02d}/{self.manager.setting_year}"

        if self.mode == "view":
            options = ["Régler", "Quitter"]
            self.display.show_date_view(
                day_str, date_str, options, self.selected_option
            )
        else:
            label = "Réglage"
            text_str = ""
            blink_field = "value"

            if self.mode == "dow":
                label = "JourSem :"
                text_str = day_str
                blink_field = "value"
            elif self.mode == "date":
                label = "Jour :"
                text_str = f"{self.manager.setting_date:02d}"
                blink_field = "value"
            elif self.mode == "month":
                label = "Mois :"
                text_str = f"{self.manager.setting_month:02d}"
                blink_field = "value"
            elif self.mode == "year":
                label = "Année :"
                text_str = f"{self.manager.setting_year}"
                blink_field = "value"

            self.display.show_settings(
                text_str, blink_field, self.blink_state, label=label
            )
