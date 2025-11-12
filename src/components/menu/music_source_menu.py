from .base_menu import BaseMenu
import time


class MusicSourceMenu(BaseMenu):
    """Menu pour choisir source musique (SD ou Webradio)."""

    def __init__(self, manager):
        super().__init__(manager)
        self.options = ["Carte SD", "Webradio", "Retour"]
        self.manager.selected_option = 0  # Par défaut SD
        self.last_render_time = 0  # Ajout pour debounce

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
                selected = self.manager.selected_option
                if selected == 0:  # Carte SD
                    self.manager._switch_to(
                        "SDCardMenu"
                    )  # Ouvre sous-menu sans switch auto
                elif selected == 1:  # Webradio
                    self.manager.music_source = "webradio"
                    self.manager.current_station_index = 0  # Index par défaut
                    self.manager.current_station_name = (
                        self.manager.webradio_stations[0]["name"]
                        if self.manager.webradio_stations
                        else "Inconnu"
                    )
                    self.manager._switch_to(
                        "SetWebradioStationMenu", mode="playback"
                    )  # Sélection station
                elif selected == 2:  # Retour
                    self.manager._switch_to("MainMenu")
                changed = True
        current_time = time.time()
        if (
            changed
            and self.manager.current_menu == self
            and current_time - self.last_render_time >= 0.1
        ):
            self.last_render_time = current_time
            self._render()

    def _render(self) -> None:
        self.display.show_menu(self.options, self.manager.selected_option)
