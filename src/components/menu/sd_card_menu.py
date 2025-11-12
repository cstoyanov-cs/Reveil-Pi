from .base_menu import BaseMenu
import time
import os


class SDCardMenu(BaseMenu):
    """Menu pour la lecture de carte SD : aléatoire ou parcourir dossiers."""

    def __init__(self, manager):
        super().__init__(manager)
        self.options = ["Lecture aléatoire", "Parcourir les dossiers", "Retour"]
        self.manager.selected_option = 0
        self.last_render_time = 0

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
                if self.manager.selected_option == 0:  # Lecture aléatoire
                    dir_path = self.manager.audio_manager.music_dir
                    # Init avec "Inconnu" ; poll Coordinator mettra à jour instantanément
                    self.manager.temp_info = self.manager.get_current_music_info()
                    self.manager.temp_display_start = time.time()
                    self.manager._render()  # Rendu initial
                    if self.manager.audio_manager.play_folder(dir_path, shuffle=True):
                        self.manager.music_source = "sd"  # Set source pour indicateurs
                        self.manager.current_menu = (
                            None  # Sortie menu, affichage temps + infos
                        )
                        self.manager._render()  # Rendu final (infos via poll)
                    else:
                        self.display.show_settings("Erreur lecture", None, True)
                        time.sleep(2)  # Délai erreur inchangé
                        self.manager.current_menu = None
                        self.manager._render()
                elif self.manager.selected_option == 1:  # Parcourir les dossiers
                    last_path = self.manager.settings.get(
                        "last_sd_path", self.manager.audio_manager.music_dir
                    )
                    if not os.path.exists(last_path):
                        last_path = self.manager.audio_manager.music_dir
                    self.manager._switch_to("SDBrowserMenu", current_path=last_path)
                elif self.manager.selected_option == 2:  # Retour
                    self.manager._switch_to("MusicSourceMenu")
                changed = True
            elif button == "menu" and event_type == "long_press":
                self.manager._switch_to("MusicSourceMenu")
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
