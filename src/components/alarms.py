from __future__ import annotations
import time
import logging
from typing import Dict, Optional, TYPE_CHECKING
from src.components.rtc import RTC
from src.components.buzzer import Buzzer

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from src.components.menu.menu_manager import MenuManager


class Alarms:
    """Gère les événements d'alarme du réveil avec logique one-shot."""

    def __init__(self, rtc: RTC, buzzer: Buzzer, audio_manager):
        self.rtc = rtc
        self.buzzer = buzzer
        self.audio_manager = audio_manager
        self.menu_manager: Optional[MenuManager] = None

        self.alarm_states = {
            1: {
                "hour": 0,
                "minute": 0,
                "enabled": False,
                "frequency": "T",
                "mode": "sd",
                "station_index": None,
            },
            2: {
                "hour": 0,
                "minute": 0,
                "enabled": False,
                "frequency": "T",
                "mode": "sd",
                "station_index": None,
            },
        }
        self.alarm_start_time: Dict[int, Optional[float]] = {
            1: None,
            2: None,
        }  # Cache timestamps déclenchement alarmes

        # One-shot tracking par minute exacte
        self.triggered_times: dict[int, Optional[str]] = {1: None, 2: None}
        self.alarm_screen_start: dict[int, Optional[float]] = {1: None, 2: None}

        # État alarme active
        self.active_alarm: Optional[int] = None
        self.active_alarm_mode: Optional[str] = None
        self.is_alarm_active: bool = False
        self.music_playing: bool = False
        self.player_shown: bool = False

        # Buzzer timeout
        self.buzzer_timer: Optional[float] = None
        self.last_stop_time: float = 0
        self.stop_cooldown: int = 60

        # Volume alarme progressif (60% → 80% → 100% sur 1min)
        self.volume_ramp_start: dict[int, Optional[float]] = {1: None, 2: None}
        self.volume_ramp_active: dict[int, bool] = {1: False, 2: False}
        self._load_alarms()

    def _load_alarms(self) -> None:
        """Charge état alarmes depuis RTC."""
        for alarm_num in [1, 2]:
            hour, minute, enabled = self.rtc.read_alarm(alarm_num)
            self.alarm_states[alarm_num]["hour"] = hour
            self.alarm_states[alarm_num]["minute"] = minute
            self.alarm_states[alarm_num]["enabled"] = enabled

    def set_alarm(
        self,
        alarm_num: int,
        hour: int,
        minute: int,
        enabled: bool,
        frequency: str = "T",
    ) -> None:
        """Règle une alarme avec reset complet du one-shot."""
        self.alarm_states[alarm_num]["hour"] = hour
        self.alarm_states[alarm_num]["minute"] = minute
        self.alarm_states[alarm_num]["enabled"] = enabled
        self.alarm_states[alarm_num]["frequency"] = frequency

        # Reset one-shot pour permettre nouveau trigger
        self.triggered_times[alarm_num] = None
        self.rtc.set_alarm(alarm_num, hour, minute, enabled)
        #
        # Reset ramp si changement alarme (évite états orphelins)

    def start_buzzer(self) -> None:
        """Active buzzer avec timeout 60s."""
        self.buzzer.activate()
        self.buzzer_timer = time.time()
        self.audio_manager.music_playing = False
        self.active_alarm_mode = "buzzer"
        self.is_alarm_active = True

    def _check_buzzer_timeout(self) -> None:
        """Vérifie timeout buzzer (60s auto-stop)."""
        if self.buzzer_timer and time.time() - self.buzzer_timer >= 60:
            self.buzzer.stop()
            self.buzzer_timer = None
            self.is_alarm_active = False
            self.active_alarm = None
            self.active_alarm_mode = None
            if self.menu_manager:
                self.menu_manager._render()

    def check_alarms(self, current_time: str) -> None:
        """
        Vérifie si alarme due et déclenche (one-shot garanti par minute).
        """
        self._check_buzzer_timeout()

        # 🎚️ RAMP VOLUME (inchangé mais expliqué)
        if self.is_alarm_active and self.active_alarm:
            alarm_num = self.active_alarm
            start_time = self.alarm_start_time.get(alarm_num)

            if (
                self.volume_ramp_active[alarm_num]
                and self.active_alarm_mode in ["sd", "webradio"]
                and start_time is not None
            ):
                elapsed = time.time() - start_time

                if elapsed >= 60.0:  # Étape 3: 100%
                    self.audio_manager.set_volume(1.0)
                    self.volume_ramp_active[alarm_num] = False
                    logger.info(f"[RAMP] A{alarm_num} → 100% (60s)")
                elif elapsed >= 30.0:  # Étape 2: 80%
                    if not hasattr(self, "_last_ramp_volume"):
                        self._last_ramp_volume = {}
                    if self._last_ramp_volume.get(alarm_num) != 0.8:
                        self.audio_manager.set_volume(0.8)
                        self._last_ramp_volume[alarm_num] = 0.8
                        logger.info(f"[RAMP] A{alarm_num} → 80% (30s)")

        # ⚠️ CORRECTION 1 : Ne check rien si alarme déjà active
        # (Une seule alarme à la fois, priorité = première déclenchée)
        if self.is_alarm_active:
            return

        current_hour, current_minute = map(int, current_time.split(":"))
        current_dow = self.rtc.read_dow()

        # ✅ CORRECTION 2 : Liste alarmes déclenchées AVANT traitement
        alarms_to_trigger = []

        for alarm_num, state in self.alarm_states.items():
            if not state["enabled"]:
                continue

            # Match heure/minute
            if state["hour"] == current_hour and state["minute"] == current_minute:
                # ONE-SHOT : Évite re-déclenchement dans même minute
                if current_time == self.triggered_times.get(alarm_num):
                    continue

                # Check fréquence
                freq = state["frequency"]
                trigger = False

                if freq == "T":
                    trigger = True
                elif freq == "S" and 2 <= current_dow <= 6:
                    trigger = True
                elif freq == "WE" and current_dow in [1, 7]:
                    trigger = True

                if trigger:
                    alarms_to_trigger.append(alarm_num)

        # ✅ CORRECTION 3 : Déclenche la PREMIÈRE alarme uniquement (priorité)
        if alarms_to_trigger:
            alarm_num = alarms_to_trigger[0]  # Priorité A1 si simultané
            state = self.alarm_states[alarm_num]

            print(f"[ALARM] Déclenchement A{alarm_num} à {current_time}")
            if len(alarms_to_trigger) > 1:
                print(f"[ALARM] ⚠️ A{alarms_to_trigger[1]} ignorée (alarme active)")

            # Marque comme déclenchée (one-shot)
            self.triggered_times[alarm_num] = current_time
            self.active_alarm = alarm_num
            self.is_alarm_active = True
            self.alarm_start_time[alarm_num] = time.time()

            # Timer écran 1h
            if self.alarm_screen_start[alarm_num] is None:
                self.alarm_screen_start[alarm_num] = time.time()

            self.active_alarm_mode = state.get("mode", "buzzer")
            if self.active_alarm_mode in ["sd", "webradio"]:
                if not self.audio_manager.ensure_mpd_available():
                    logger.warning(
                        f"[ALARM] MPD down au trigger A{alarm_num} → Fallback buzzer"
                    )
                    self.active_alarm_mode = "buzzer"
                    self.start_buzzer()
                    return
            success = False

            # Volume 60% avant play (SD/Webradio uniquement)
            if state.get("mode") in ["sd", "webradio"]:
                self.audio_manager.set_volume(0.6)
                logger.info(f"[ALARM] A{alarm_num} volume init → 60%")

            # ===== DÉCLENCHEMENT SELON MODE =====
            if self.active_alarm_mode == "webradio":
                index = state.get("station_index", 0)
                success = self.audio_manager.play_webradio_station(index)

                if success:
                    time.sleep(2.0)
                    if self.menu_manager:
                        self.menu_manager.music_source = "webradio"
                        self.menu_manager.current_station_name = (
                            self.menu_manager.webradio_stations[index]["name"]
                        )
                        self.menu_manager.music_start_time = time.time()
                        self.music_playing = True
                else:
                    # Fallback SD
                    print("[ALARM] Webradio échec -> Fallback SD")
                    time.sleep(2.0)
                    self.active_alarm_mode = "sd"
                    success = self.audio_manager.play_random_music()

                    if success and self.menu_manager:
                        self.menu_manager.music_source = "sd"
                        self.music_playing = True

            elif self.active_alarm_mode == "sd":
                success = self.audio_manager.play_random_music()
                if success and self.menu_manager:
                    self.menu_manager.music_source = "sd"
                    self.menu_manager.music_start_time = time.time()
                    self.music_playing = True

            # Fallback buzzer si tout échoue
            if not success:
                print("[ALARM] Fallback buzzer")
                self.active_alarm_mode = "buzzer"
                self.start_buzzer()

            # Init ramp volume si musique lancée
            if success and self.active_alarm_mode in ["sd", "webradio"]:
                self.volume_ramp_active[alarm_num] = True

            # Render final
            if self.menu_manager:
                self.menu_manager._render()

        # ✅ CORRECTION 4 : Reset triggered_times APRÈS traitement
        # (Évite race condition entre reset et check A2)
        for alarm_num in [1, 2]:
            if (
                self.triggered_times[alarm_num] is not None
                and self.triggered_times[alarm_num] != current_time
            ):
                self.triggered_times[alarm_num] = None

    def _activate_alarm_playback(self, alarm_num: int, state: dict) -> bool:
        """
        Active la lecture d'alarme selon le mode configuré.
        Gère fallbacks automatiques: webradio → SD → buzzer.

        Args:
            alarm_num: Numéro alarme (1 ou 2)
            state: Dict d'état de l'alarme

        Returns:
            True si succès (musique ou buzzer actif)
        """
        mode = state.get("mode", "buzzer")

        # Vérif MPD si mode musical
        if mode in ["sd", "webradio"]:
            if not self.audio_manager.ensure_mpd_available():
                logger.warning(
                    f"[ALARM] MPD down au trigger A{alarm_num} → Fallback buzzer direct"
                )
                self._activate_buzzer_mode()
                return True  # Buzzer = succès

        # === WEBRADIO ===
        if mode == "webradio":
            index = state.get("station_index", 0)
            self.active_alarm_mode = "webradio"

            # Volume init 60%
            self.audio_manager.set_volume(0.6)
            logger.info(f"[ALARM] A{alarm_num} volume init → 60%")

            success = self.audio_manager.play_webradio_station(index)

            if success:
                time.sleep(2.0)  # Buffer réseau
                # ✅ Sync état complet
                if self.menu_manager:
                    self.menu_manager.music_source = "webradio"
                    self.menu_manager.current_station_name = (
                        self.menu_manager.webradio_stations[index]["name"]
                    )
                    self.menu_manager.music_start_time = time.time()
                self.music_playing = True
                self.volume_ramp_active[alarm_num] = True
                logger.info(f"[ALARM] A{alarm_num} webradio OK")
                return True
            else:
                # Fallback SD
                logger.warning(f"[ALARM] A{alarm_num} webradio échec → Fallback SD")
                time.sleep(2.0)
                mode = "sd"  # Continue vers SD

        # === SD (direct ou fallback) ===
        if mode == "sd":
            self.active_alarm_mode = "sd"

            # Volume init 60%
            self.audio_manager.set_volume(0.6)
            logger.info(f"[ALARM] A{alarm_num} volume init → 60%")

            success = self.audio_manager.play_random_music()

            if success:
                # ✅ Sync état complet (MÊME EN FALLBACK)
                if self.menu_manager:
                    self.menu_manager.music_source = "sd"
                    self.menu_manager.music_start_time = time.time()
                self.music_playing = True
                self.volume_ramp_active[alarm_num] = True
                logger.info(f"[ALARM] A{alarm_num} SD OK")
                return True
            else:
                # Fallback buzzer
                logger.warning(f"[ALARM] A{alarm_num} SD échec → Fallback buzzer")

        # === BUZZER (direct ou fallback final) ===
        self._activate_buzzer_mode()
        logger.info(f"[ALARM] A{alarm_num} buzzer actif")
        return True

    def _activate_buzzer_mode(self) -> None:
        """Active le mode buzzer (helper pour fallback)."""
        self.active_alarm_mode = "buzzer"
        self.buzzer.activate()
        self.buzzer_timer = time.time()
        self.music_playing = False
        if self.menu_manager:
            self.menu_manager.music_source = None  # ✅ Cleanup source

    def stop(self) -> None:
        """
        Arrête l'alarme en cours SANS reset triggered_times.

        CRITICAL : triggered_times garde la minute actuelle pour éviter
        re-déclenchement en boucle. Il se reset automatiquement au
        changement de minute dans check_alarms().
        """
        if not self.is_alarm_active:
            return

        print(f"[ALARM] Arrêt A{self.active_alarm}")

        # Stop audio/buzzer
        if self.active_alarm_mode in ["sd", "webradio"]:
            self.audio_manager.stop()
        elif self.active_alarm_mode == "buzzer":
            self.buzzer.stop()

        #  NE PAS reset triggered_times (évite boucle infinie)
        # Il sera reset automatiquement au changement de minute

        #  Reset alarm_screen_start pour réactiver veille normale
        if self.active_alarm is not None:
            self.alarm_screen_start[self.active_alarm] = None

        # Reset flags état alarme
        self.is_alarm_active = False
        self.active_alarm = None
        self.active_alarm_mode = None
        self.player_shown = False

        self.music_playing = False

        # Reset cache volume
        if hasattr(self, "_last_ramp_volume") and self.active_alarm:
            self._last_ramp_volume.pop(self.active_alarm, None)

        # Reset ramp volume à 100% (session normale)
        if self.active_alarm:
            self.audio_manager.set_volume(1.0)
            logger.info(
                f"[ALARM] Reset volume MPD → 100% après arrêt A{self.active_alarm}"
            )

        # Render non-bloquant
        try:
            if self.menu_manager:
                self.menu_manager._render()
        except Exception as e:
            print(f"[WARN] Render après stop: {e}")

    def get_indicators(self) -> tuple[tuple[bool, bool], tuple[str, str]]:
        """Retourne indicateurs et fréquences pour affichage."""
        indicators = (self.alarm_states[1]["enabled"], self.alarm_states[2]["enabled"])
        frequencies = (
            self.alarm_states[1]["frequency"],
            self.alarm_states[2]["frequency"],
        )
        return indicators, frequencies
