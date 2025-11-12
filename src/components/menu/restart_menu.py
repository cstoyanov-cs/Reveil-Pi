import subprocess
import time
import logging
from .base_menu import BaseMenu
from typing import List, Dict

logger = logging.getLogger(__name__)


class RestartMenu(BaseMenu):
    def __init__(self, manager):
        super().__init__(manager)
        self.options = ["Confirmer redémarrage", "Annuler"]
        self.manager.selected_option = 0  # Par défaut confirmer

    def handle_input(self, events: List[Dict[str, str]], blink_interval: float) -> None:
        self._update_blink(blink_interval)
        changed = False
        for event in events:
            button, event_type = event["button"], event["type"]
            if button in ["up", "down"] and event_type == "short_press":
                self.manager.selected_option = (self.manager.selected_option + 1) % len(
                    self.options
                )
                changed = True
            elif button == "menu" and event_type == "short_press":
                if self.manager.selected_option == 0:  # Confirmer seulement
                    self._confirm_restart()  # SOLID: Appel à méthode dédiée (SRP)
                # Toujours quitter sur short_press (reboot ou annule)
                self.manager.current_menu = None
                changed = True
            elif button == "menu" and event_type == "long_press":
                self.manager._switch_to("SettingsMenu")  # Retour settings
        if changed:
            self._render()

    def _confirm_restart(self) -> None:
        """Méthode dédiée au cleanup et reboot (SRP: isolé des événements UI)."""
        try:
            # Arrêt propre MPD avant reboot
            self.manager.audio_manager.cleanup()
            logger.info("[RESTART] MPD arrêté proprement avant reboot")
        except Exception as e:
            logger.warning(f"[RESTART] Erreur arrêt MPD: {e}")

        try:
            result = subprocess.run(
                ["sudo", "reboot"],
                check=True,
                capture_output=True,
                timeout=5.0,
            )
            if result.returncode != 0:
                logger.error(
                    f"[RESTART] Reboot failed: rc={result.returncode}, out={result.stdout.decode()}"
                )
                self.display.show_settings("Erreur redémarrage", None, True)
                time.sleep(2)
        except subprocess.TimeoutExpired:
            logger.error("[RESTART] Reboot timeout")
            self.display.show_settings("Timeout reboot", None, True)
            time.sleep(2)
        except subprocess.CalledProcessError as e:
            logger.error(f"[RESTART] Reboot error: {e}")
            self.display.show_settings("Erreur redémarrage", None, True)
            time.sleep(2)

    def _render(self) -> None:
        self.display.show_menu(self.options, self.manager.selected_option)
