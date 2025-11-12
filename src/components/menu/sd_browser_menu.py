import os
import time
from .base_menu import BaseMenu


class SDBrowserMenu(BaseMenu):
    """Navigateur de fichiers pour carte SD."""

    def __init__(self, manager, current_path: str):
        super().__init__(manager)
        self.current_path = current_path
        self.options = self._list_directory() + ["Retour"]
        self.manager.selected_option = 0
        self.last_render_time = (
            0  # Ajout pour limiter les rendus redondants lors des transitions
        )

    def _list_directory(self) -> list[str]:
        """Liste dossiers et fichiers triés, avec icônes."""
        try:
            items = os.listdir(self.current_path)
        except OSError as e:
            print(f"Erreur lecture dossier {self.current_path}: {e}")
            return ["Erreur dossier", "Retour"]

        dirs = [
            f"📁 {item}"
            for item in items
            if os.path.isdir(os.path.join(self.current_path, item))
        ]
        files = [
            f"🎵 {item}"
            for item in items
            if os.path.isfile(os.path.join(self.current_path, item))
        ]
        return sorted(dirs) + sorted(files)  # Dossiers en haut

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
                selected = self.options[self.manager.selected_option]

                if selected == "Retour":
                    if self.current_path == self.manager.audio_manager.music_dir:
                        self.manager._switch_to("SDCardMenu")  # Retour à Carte SD
                    else:
                        parent = os.path.dirname(self.current_path)
                        if parent:  # Évite remontée au-dessus de la racine
                            self.manager._switch_to(
                                "SDBrowserMenu", current_path=parent
                            )
                        else:
                            self.manager._switch_to("SDCardMenu")
                    changed = True
                else:
                    # Gestion robuste des icônes Unicode
                    # Enlève l'icône (premiers caractères jusqu'au premier espace)
                    if selected.startswith("📁 ") or selected.startswith("🎵 "):
                        item_name = selected[2:]  # Enlève "📁 " ou "🎵 "
                    else:
                        # Fallback si icône différente
                        item_name = (
                            selected.split(" ", 1)[-1] if " " in selected else selected
                        )

                    item_path = os.path.join(self.current_path, item_name)

                    if os.path.isdir(item_path):
                        # Entre dans le dossier
                        self.manager._switch_to("SDBrowserMenu", current_path=item_path)
                        changed = True
                    elif os.path.isfile(
                        item_path
                    ):  #  Aligné avec if (indent 20 espaces)
                        # Lecture séquentielle du dossier depuis le début
                        filename = os.path.basename(item_path)
                        if self.manager.audio_manager.play_file_sequential(
                            item_path, self.current_path
                        ):
                            self.manager.music_source = "sd"
                            self.manager.music_start_time = time.time()
                            #  Init dict minimal (trigger coordinator pour full après 1s, évite doublon simple)
                            self.manager.temp_info = {
                                "artist": "Chargement...",
                                "title": filename,
                                "elapsed": "0:00",
                                "total": "0:00",
                                "progress": 0.0,
                                "is_playing": True,
                                "source": "sd",
                            }
                            self.manager.temp_display_start = time.time()
                            self.manager.current_menu = None
                            # Pas de _render() : coordinator gère (évite conflit UI)
                        else:
                            self.display.show_settings("Erreur lecture", None, True)
                            time.sleep(2)
                            self.manager.current_menu = None
                            self.manager._render()  # Seul sur erreur
                        changed = True
                    else:  #  Aligné avec if/elif (indent 20 espaces, pour item invalide)
                        # Item invalide (fichier supprimé entre temps)
                        self.display.show_settings("Fichier absent", None, True)
                        time.sleep(1)
                        changed = True

            elif button == "menu" and event_type == "long_press":
                # Long press : retour rapide
                if self.current_path == self.manager.audio_manager.music_dir:
                    self.manager._switch_to("SDCardMenu")
                else:
                    parent = os.path.dirname(self.current_path)
                    if parent:
                        self.manager._switch_to("SDBrowserMenu", current_path=parent)
                    else:
                        self.manager._switch_to("SDCardMenu")
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
        """Affiche le menu du navigateur de fichiers."""
        self.display.show_menu(self.options, self.manager.selected_option)
