from .base_menu import BaseMenu
import subprocess
import time


class MusicPlayerMenu(BaseMenu):
    def __init__(self, manager):
        super().__init__(manager)
        self.play_music()  # Lance la musique aléatoire à l'entrée
        self.last_info_time = 0  # Pour rafraîchissement périodique
        self.current_info = "Carte sd: Chargement..."

    def play_music(self):
        self.manager.alarm_manager.play_random_music()  # Réutilise la méthode existante
        self.manager.music_source = "sd"

    def get_current_info(self):
        try:
            output = subprocess.check_output(["mocp", "-i"]).decode().strip()
            lines = output.split("\n")
            info = {
                line.split(": ", 1)[0]: line.split(": ", 1)[1]
                for line in lines
                if ": " in line
            }
            artist = info.get("Artist", "Inconnu")
            title = info.get("SongTitle", info.get("Title", "Inconnu"))
            current = info.get("CurrentTime", "00:00")
            total = info.get("TotalTime", "00:00")
            return f"Carte SD\nArtiste: {artist}\nTitre: {title}\n{current}/{total}"
        except Exception:
            return "Carte SD\nArtiste: Inconnu\nTitre: Inconnu\n00:00/00:00"

    def handle_input(self, events: list[dict], blink_interval: float) -> None:
        _ = blink_interval  # Inutilisé ici
        current_time = time.time()
        changed = False
        for event in events:
            button, event_type = event["button"], event["type"]
            if button == "up" and event_type == "short_press":
                subprocess.run(["mocp", "-f"])  # Next track
                changed = True
            elif button == "down" and event_type == "short_press":
                subprocess.run(["mocp", "-r"])  # Previous track
                changed = True
            elif button == "menu" and event_type == "short_press":
                self.manager._switch_to("MainMenu")  # Ouvre menu sans stop
            elif button == "menu" and event_type == "long_press":
                self.manager.alarm_manager.stop()  # Stop sans ouvrir
                self.manager.current_menu = None

        # Rafraîchissement infos musique toutes les secondes
        if current_time - self.last_info_time >= 1:
            self.current_info = self.get_current_info()
            self.last_info_time = current_time
            changed = True

        if changed:
            self._render()

    def _render(self) -> None:
        self.display.show_settings(self.current_info, None, True)
