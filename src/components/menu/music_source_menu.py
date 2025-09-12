from .base_menu import BaseMenu
import time


class MusicSourceMenu(BaseMenu):
    """Menu pour choisir source musique (SD ou Webradio)."""

    def __init__(self, manager):
        super().__init__(manager)
        self.options = ["Carte SD", "Webradio", "Retour"]
        self.manager.selected_option = 0  # Par défaut SD

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
                    self.manager.music_source = "sd"  # Track source
                    self.manager.show_time_after_timeout = (
                        False  # Réinitialiser timeout
                    )
                    if self.manager.audio_manager.play_random_music():  # Joue SD
                        self.manager.music_start_time = time.time()
                        self.manager.temp_info = self.manager.get_current_music_info()
                        self.manager.temp_display_start = time.time()
                    else:
                        print("Erreur lecture SD")
                    self.manager.current_menu = None  # Retour à normal
                    self.manager._render()  # Force affichage
                elif selected == 1:  # Webradio
                    self.manager.music_source = "webradio"
                    self.manager.show_time_after_timeout = (
                        False  # Réinitialiser timeout
                    )
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
            elif button == "menu" and event_type == "long_press":
                self.manager.alarm_manager.stop()  # Arrêt musique si en cours
                self.manager.current_menu = None  # Retour à normal
                changed = True
        if changed:
            self._render()

    def _render(self) -> None:
        self.display.show_menu(self.options, self.manager.selected_option)
