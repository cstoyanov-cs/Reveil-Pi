import subprocess
import time
import re
from .base_menu import BaseMenu


class MusicPlayerMenu(BaseMenu):
    def __init__(self, manager):
        super().__init__(manager)

    def get_current_info(self):
        try:
            # Récupérer status pour position/duration
            status_output = (
                subprocess.check_output(["mpc", "status"], stderr=subprocess.PIPE)
                .decode()
                .strip()
            )
            # Parser temps avec regex (ex: [playing] #1/1   1:30/3:00 (50%))
            time_match = re.search(r"(\d+:\d+)/(\d+:\d+)", status_output)
            current = time_match.group(1) if time_match else "00:00"
            total = time_match.group(2) if time_match else "00:00"

            # Récupérer artist/title
            current_output = (
                subprocess.check_output(
                    ["mpc", "current", "--format", "%artist% - %title%"],
                    stderr=subprocess.PIPE,
                )
                .decode()
                .strip()
            )
            if not current_output or current_output == "-":
                artist = "Inconnu"
                title = "Inconnu"
            else:
                artist, title = (
                    current_output.split(" - ", 1)
                    if " - " in current_output
                    else ("Inconnu", current_output)
                )

            return f"Carte SD\nArtiste: {artist}\nTitre: {title}\n{current}/{total}"
        except subprocess.CalledProcessError:
            return "Carte SD\nArtiste: Inconnu\nTitre: Inconnu\n00:00/00:00"

    def handle_input(self, events: list[dict], blink_interval: float) -> None:
        _ = blink_interval  # Inutilisé ici
        current_time = time.time()
        self.manager.temp_info = self.manager.get_current_music_info()
        self.manager.temp_display_start = current_time
        changed = False
        for event in events:
            button, event_type = event["button"], event["type"]
            if button == "up" and event_type == "short_press":
                success = self.manager.controls.next_track()
                if success:
                    changed = True
            elif button == "down" and event_type == "short_press":
                success = self.manager.controls.prev_track()
                if success:
                    changed = True
            elif button == "menu" and event_type == "short_press":
                self.manager._switch_to("MainMenu")  # Ouvre menu sans stop
            elif button == "menu" and event_type == "long_press":
                self.manager.alarm_manager.stop()  # Stop sans ouvrir
                self.manager.current_menu = None
                self.manager.temp_display_start = current_time
        # Rafraîchissement infos musique toutes les secondes
        if changed:
            self._render()
            self.manager.temp_info = self.manager.get_current_music_info()
            self.manager.temp_display_start = time.time()

    def _render(self) -> None:
        info = self.manager.get_current_music_info()
        self.display.show_settings(info, None, True, label="Contrôles musique")
