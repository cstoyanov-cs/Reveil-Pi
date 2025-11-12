import subprocess
import time
from typing import Union, Dict, Any
from src.components.time import Time
from src.components.alarms import Alarms
from src.components.menu.menu_manager import MenuManager
from src.components.rotary import RotaryEncoder
from src.components.display import Display
from src.components.audio_manager import AudioManager
import logging

logger = logging.getLogger(__name__)


class Coordinator:
    """Coordonne les interactions entre les composants du réveil."""

    def __init__(
        self,
        time_manager: Time,
        alarm_manager: Alarms,
        menu_manager: MenuManager,
        rotary: RotaryEncoder,
        display: Display,
        config: dict,
        audio_manager: AudioManager,
    ):
        self.time_manager = time_manager
        self.alarm_manager = alarm_manager
        self.menu_manager = menu_manager
        self.menu_manager.coordinator = (
            self  # Référence circulaire pour la gestion des menus
        )
        self.rotary = rotary
        self.display = display
        self.display.manager = (
            menu_manager  # Associe le gestionnaire de menu à l'affichage
        )
        self.config = config
        self.audio_manager = audio_manager
        self.last_temp_timeout_check = 0  # Dernier check timeout infos musique
        self.loop_delay = config["general"][
            "main_loop_delay"
        ]  # Délai principal de la boucle
        self.last_mpd_warning = 0  # Dernier warning MPD
        self.last_flag_sync = 0
        self.mpd_fallback_active = False  # Flag fallback buzzer unique
        # Optimisation cache
        self.cached_time = "00:00"
        self.last_time_read = 0
        self.boot_time: float = time.time()  # Timestamp boot réveil
        self.mpd_first_check_delay: float = (
            180.0  # Premiere vérif mpd au bout de  3 minutes
        )
        self.mpd_first_check_done: bool = False

    def reset_activity(self) -> None:
        """Réinitialise le timer d'activité et allume l'écran."""
        self.menu_manager.last_activity = time.time()
        self.display.power_on()

    def _handle_screen_saver(self, current_time: float) -> bool:
        """Gère la veille. Bypass si alarme active et < alarm_screen_on_time (1h). Retourne True si changement."""
        changed = False
        if not self.menu_manager.settings["screen_saver_enabled"]:
            return changed
        # Check alarme active pour forcer écran allumé 1h
        if self.alarm_manager.is_alarm_active and self.alarm_manager.active_alarm:
            alarm_num = self.alarm_manager.active_alarm
            if self.alarm_manager.alarm_screen_start[alarm_num] is not None:
                screen_duration = self.menu_manager.settings.get(
                    "alarm_screen_on_time", 3600
                )  # 1h défaut
                start_time = self.alarm_manager.alarm_screen_start[
                    alarm_num
                ]  # Cache pour typage
                if start_time is not None:
                    elapsed = current_time - start_time
                    if elapsed < screen_duration:
                        if not self.display.is_on:
                            self.display.power_on()
                            changed = True
                    self.menu_manager.last_activity = (
                        current_time  # Reset timer activité
                    )
                    return changed  # Sort tôt, pas de veille
                else:
                    # Timeout 1h écoulé : reset et autorise veille normale
                    self.alarm_manager.alarm_screen_start[alarm_num] = None
        # Logique veille normale (menus/inactivité)
        if self.menu_manager.current_menu is not None:
            # Menu ouvert : allume si off, reset activity SEULEMENT si allumage forcé
            was_off = not self.display.is_on
            if was_off:
                self.display.power_on()
                changed = True
                self.menu_manager.last_activity = (
                    current_time  # Reset seulement sur allumage
                )
            # Pas de reset sinon : laisse inactivité monter pour timeout menu
        else:
            # Pas de menu : check timeout standard
            timeout = self.menu_manager.settings["screen_timeout"]  # 30s
            if current_time - self.menu_manager.last_activity > timeout:
                if self.display.is_on:
                    self.display.power_off()
                    changed = True
            else:
                if not self.display.is_on:
                    self.display.power_on()
                    changed = True
        return changed

    def run(self) -> None:
        """Boucle principale pour la gestion des événements et des mises à jour."""
        try:
            last_temp_info = None
            last_info_check = 0
            last_saver_check = 0
            last_render_time = 0
            render_throttle = 0.2  # Max 5 FPS pour l'écran
            render_needed = False

            while True:
                current_time = time.time()

                # ====== CHECK TEMPS + ALARMES (toujours actif) ======
                if current_time - self.last_time_read >= 1.0:
                    self.cached_time = self.time_manager.get_time()
                    self.last_time_read = current_time
                    # Check alarmes sur nouvelle minute
                    self.alarm_manager.check_alarms(self.cached_time)

                # ====== CHECK DURÉE MAX ALARME (toujours actif) ======
                if (
                    self.alarm_manager.is_alarm_active
                    and self.alarm_manager.active_alarm
                ):
                    alarm_num = self.alarm_manager.active_alarm
                    start_time = self.alarm_manager.alarm_start_time.get(alarm_num)

                    if (
                        start_time
                        and current_time - start_time
                        > self.menu_manager.settings["alarm_max_duration"]
                    ):
                        logger.info(
                            f"[ALARM] Max duration exceeded → Stop alarme {alarm_num}"
                        )
                        self.alarm_manager.stop()

                # Allumage écran sur alarme
                if (
                    self.alarm_manager.is_alarm_active
                    and not self.display.is_on
                    and self.alarm_manager.active_alarm is not None
                ):
                    logger.debug("[COORDINATOR] Alarme active → Allumage écran forcé")
                    self.display.power_on()
                    render_needed = True

                # ====== SYNC FLAG MPD (toujours actif) ======
                if current_time - self.last_flag_sync >= 5.0:
                    self.menu_manager.mpd_unavailable = (
                        self.audio_manager.mpd_unavailable
                    )
                    self.last_flag_sync = current_time

                # ====== INPUT UTILISATEUR (toujours actif) ======
                events = self.rotary.get_events()

                self.menu_manager.handle_input(
                    events, self.config["display"]["blink_interval"]
                )

                if events:
                    render_needed = True

                # ====== MUSIQUE (toujours actif) ======
                if (
                    self.audio_manager.music_playing
                    and current_time - last_info_check >= 1.0
                ):
                    new_temp_info = self._update_music_info()
                    last_info_check = current_time
                    needs_update = False

                    if new_temp_info is not None:
                        if last_temp_info is None:
                            needs_update = True
                        elif isinstance(new_temp_info, dict) and isinstance(
                            last_temp_info, dict
                        ):
                            if (
                                new_temp_info.get("artist")
                                != last_temp_info.get("artist")
                                or new_temp_info.get("title")
                                != last_temp_info.get("title")
                                or new_temp_info.get("is_playing")
                                != last_temp_info.get("is_playing")
                            ):
                                needs_update = True
                        else:
                            needs_update = True

                    # Pendant alarme : une seule fois
                    if self.alarm_manager.is_alarm_active:
                        if not self.alarm_manager.player_shown:
                            self.menu_manager.temp_info = new_temp_info
                            self.menu_manager.temp_display_start = current_time
                            if last_temp_info is not None:
                                del last_temp_info
                            if isinstance(new_temp_info, dict):
                                last_temp_info = new_temp_info.copy()
                            else:
                                last_temp_info = new_temp_info
                            del new_temp_info
                            render_needed = True
                            self.alarm_manager.player_shown = True
                        else:
                            # Maj silencieuse progression
                            if (
                                self.menu_manager.temp_info is not None
                                and isinstance(self.menu_manager.temp_info, dict)
                                and isinstance(new_temp_info, dict)
                            ):
                                for k in ["elapsed", "progress"]:
                                    if k in new_temp_info:
                                        self.menu_manager.temp_info[k] = new_temp_info[
                                            k
                                        ]
                            del new_temp_info
                    else:
                        # Hors alarme
                        if needs_update:
                            if self.menu_manager.temp_info is not None:
                                del self.menu_manager.temp_info
                            self.menu_manager.temp_info = new_temp_info
                            self.menu_manager.temp_display_start = current_time
                            if isinstance(new_temp_info, dict):
                                if last_temp_info is not None:
                                    del last_temp_info
                                last_temp_info = new_temp_info.copy()
                            else:
                                last_temp_info = new_temp_info
                            del new_temp_info
                            render_needed = True
                        else:
                            # Maj silencieuse
                            if (
                                self.menu_manager.temp_info is not None
                                and isinstance(self.menu_manager.temp_info, dict)
                                and isinstance(new_temp_info, dict)
                            ):
                                for k in ["elapsed", "progress"]:
                                    if k in new_temp_info:
                                        self.menu_manager.temp_info[k] = new_temp_info[
                                            k
                                        ]
                            del new_temp_info

                # ====== TIMEOUT INFOS MUSIQUE (toujours actif) ======
                temp_timeout = self.menu_manager.settings.get("temp_info_timeout", 15)
                if current_time - self.last_temp_timeout_check >= 1.0:
                    self.last_temp_timeout_check = current_time
                    if (
                        self.menu_manager.temp_info is not None
                        and self.menu_manager.temp_display_start is not None
                        and current_time - self.menu_manager.temp_display_start
                        > temp_timeout
                        and not self.alarm_manager.is_alarm_active
                    ):
                        self.menu_manager.temp_info = None
                        self.menu_manager.temp_display_start = None
                        render_needed = True

                # ====== VEILLE ÉCRAN (toujours actif) ======
                if (
                    self.menu_manager.settings["screen_saver_enabled"]
                    and current_time - last_saver_check >= 1.0
                ):
                    last_saver_check = current_time
                    saver_changed = self._handle_screen_saver(current_time)
                    if saver_changed:
                        render_needed = True

                # ====== RENDER (toujours actif) ======
                if (render_needed or self.menu_manager.current_menu is not None) and (
                    current_time - last_render_time >= render_throttle
                ):
                    self.menu_manager._render()
                    render_needed = False
                    last_render_time = current_time

                # ====== PAUSE BOUCLE (toujours actif) ======
                time.sleep(self.loop_delay)

        except Exception as e:
            logger.error(f"[ERROR {time.time():.3f}] Erreur coordinateur : {e}")
            if self.display.device:
                self.display.show_time("Erreur", (False, False), ("", ""))

    def _update_music_info(self) -> Union[Dict[str, Any], str, None]:
        """
        Met à jour les informations musicales avec structure détaillée.
        Returns:
            dict avec infos détaillées, ou None si erreur
        """
        # Wrap subprocess pour timeout (exemple si get_detailed utilise check_output)
        try:
            return self.audio_manager.get_detailed_track_info()
        except subprocess.TimeoutExpired:
            print("[ERROR] MPD timeout in music info")
            return None
