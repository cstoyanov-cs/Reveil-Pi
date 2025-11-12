import subprocess
import time
from .base_menu import BaseMenu


class SSHMenu(BaseMenu):
    def __init__(self, manager):
        super().__init__(manager)
        self.action = None  # 'enable' ou 'disable' (Option[str])
        self.confirming = False  # Flag confirmation (simule sous-menu)
        self.options = self._get_main_options()  # Charge dynamique
        self.manager.selected_option = 0  # Statut par défaut
        self._render()  # Affichage initial

    @staticmethod
    def get_ssh_status() -> bool:
        """Vérifie si SSH est actif (sans sudo)."""
        try:
            result = subprocess.run(
                ["systemctl", "is-active", "ssh"], capture_output=True, text=True
            )
            return result.returncode == 0 and "active" in result.stdout.strip()
        except Exception as e:
            print(f"Erreur vérif statut SSH: {e}")
            return False  # Fallback

    def _get_main_options(self) -> list:  # Ligne 28
        is_active = SSHMenu.get_ssh_status()  # Ligne 29: Cache status
        status = "Activé" if is_active else "Désactivé"  # Ligne 30
        action_label = (
            "Stop SSH" if is_active else "Start SSH"
        )  # Ligne 31: Label intuitif
        return [  # Ligne 32
            f"Statut: {status}",  # Ligne 33: Info fixe (non actionable)
            action_label,  # Ligne 34: Action dynamique
            "Retour",  # Ligne 35: À SettingsMenu
        ]

    def _execute_ssh_action(self, action: str) -> bool:
        """Exécute avec sudo (assume NOPASSWD)."""
        try:
            cmd = [
                "sudo",
                "systemctl",
                action,
                "--now",
                "ssh",
            ]  # Enable/disable + start/stop immédiat
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                print(f"Erreur SSH {action}: {result.stderr}")
                return False
            return True
        except subprocess.TimeoutExpired:
            print("Timeout commande SSH")
            return False
        except Exception as e:
            print(f"Erreur exécution SSH: {e}")
            return False

    def handle_input(self, events: list[dict], blink_interval: float) -> None:
        self._update_blink(blink_interval)
        changed = False
        for event in events:
            button, event_type = event["button"], event["type"]
            if self.confirming:  # Confirmation ["Oui", "Non"]
                if button in ["up", "down"] and event_type == "short_press":
                    self.manager.selected_option = (
                        self.manager.selected_option + (1 if button == "up" else -1)
                    ) % 2
                    changed = True
                elif button == "menu" and event_type == "short_press":
                    if self.manager.selected_option == 0:  # Oui : Exécute
                        if self.action is None:  # Garde Pyright
                            self.confirming = False
                            self.options = self._get_main_options()
                            self.manager.selected_option = 0
                            changed = True
                            continue
                        success = self._execute_ssh_action(self.action)
                        msg = (
                            f"SSH {'activé' if self.action == 'enable' else 'désactivé'}"
                            if success
                            else "Erreur action SSH"
                        )
                        self.manager.temp_info = msg  # 15s affichage
                        self.manager.temp_display_start = time.time()
                        self.confirming = False
                        self.options = self._get_main_options()
                        self.manager.selected_option = 0
                    else:  # Non : Annule
                        self.action = None  # Reset après annulation
                        self.confirming = False
                        self.options = self._get_main_options()
                        self.manager.selected_option = 1
                    changed = True
            else:  # Principal
                if button in ["up", "down"] and event_type == "short_press":
                    self.manager.selected_option = (
                        self.manager.selected_option + (1 if button == "down" else -1)
                    ) % len(self.options)
                    changed = True
                elif button == "menu" and event_type == "short_press":
                    if self.manager.selected_option == 0:  # Statut : Ignore
                        pass
                    elif self.manager.selected_option == 1:  # Toggle
                        # Determine action based on current SSH status
                        self.action = (
                            "disable" if SSHMenu.get_ssh_status() else "enable"
                        )
                        self.confirming = True
                        self.options = ["Oui", "Non"]
                        self.manager.selected_option = 0
                        changed = True
                    elif self.manager.selected_option == 2:  # Retour
                        self.manager._switch_to("SettingsMenu")
                elif button == "menu" and event_type == "long_press":  # Sortie
                    self.manager.current_menu = None
                    self.action = None  # Reset
                    changed = True
            if changed:
                self._render()

    def _render(self) -> None:  # Ligne 110
        self.display.show_menu(self.options, self.manager.selected_option)
