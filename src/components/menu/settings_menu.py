from .base_menu import BaseMenu
from .ssh_menu import SSHMenu  # Ligne 45: Import pour get_ssh_status statique


class SettingsMenu(BaseMenu):
    def __init__(self, manager):
        super().__init__(manager)
        self.options = [
            "Veille active",
            "Temps veille (s)",
            "Temps menu (s)",
            "Temps écran alarme (s)",
            "Durée max alarme (s)",
            "Lecture",
            "Redémarrer le réveil",
            "Service SSH",
            "Quitter",
        ]
        self.manager.selected_option = 0

    @staticmethod
    def format_time(val: int) -> str:
        if val >= 3600:
            return f"{val // 3600}h"  # Heures
        elif val >= 60:
            return f"{val // 60}m"  # Minutes
        return f"{val}s"  # Secondes

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
                if self.manager.selected_option == 0:
                    self.manager.settings[
                        "screen_saver_enabled"
                    ] = not self.manager.settings["screen_saver_enabled"]
                    self.manager.save_params()
                    changed = True
                elif self.manager.selected_option == 1:
                    self.manager._switch_to(
                        "SetParamMenu",
                        param_key="screen_timeout",
                        min_val=10,
                        max_val=300,
                    )
                elif self.manager.selected_option == 2:
                    self.manager._switch_to(
                        "SetParamMenu",
                        param_key="menu_timeout",
                        min_val=10,
                        max_val=300,
                    )
                elif self.manager.selected_option == 3:
                    self.manager._switch_to(
                        "SetParamMenu",
                        param_key="alarm_screen_on_time",
                        min_val=300,
                        max_val=7200,
                    )
                elif self.manager.selected_option == 4:
                    self.manager._switch_to(
                        "SetParamMenu",
                        param_key="alarm_max_duration",
                        min_val=1800,
                        max_val=14400,
                    )
                elif self.manager.selected_option == 5:  # Lecture
                    self.manager._switch_to("PlaybackModeMenu")

                elif self.manager.selected_option == 6:  # Redémarrer
                    self.manager._switch_to("RestartMenu")

                elif self.manager.selected_option == 7:  # Service SSH
                    self.manager._switch_to("SSHMenu")

                elif self.manager.selected_option == 8:
                    self.manager._switch_to("MainMenu")
                    self.manager.selected_option = 3  # Retour à "Paramètres" position
        if changed:
            self._render()

    def _render(self) -> None:
        # Afficher options avec valeurs actuelles
        mode_str = (
            "Séquentiel"
            if self.manager.settings["playback_mode"] == "sequentiel"
            else "Aléatoire"
        )  #  Défini ici, avant la liste
        opts_with_values = [
            f"Veille active: {'Oui' if self.manager.settings['screen_saver_enabled'] else 'Non'}",
            f"Temps veille: {self.format_time(self.manager.settings['screen_timeout'])}",
            f"Temps menu: {self.format_time(self.manager.settings['menu_timeout'])}",
            f"Écran alarme: {self.format_time(self.manager.settings['alarm_screen_on_time'])}",
            f"Max alarme: {self.format_time(self.manager.settings['alarm_max_duration'])}",
            f"Mode lecture: {mode_str}",
            "Redémarrer le réveil",  # Index 6 (statique, pas de valeur)
            f"Service SSH: {'Activé' if SSHMenu.get_ssh_status() else 'Désactivé'}",  # Ligne 65: Appel statique
            "Quitter",
        ]
        self.display.show_menu(opts_with_values, self.manager.selected_option)
