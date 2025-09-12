from __future__ import annotations
import time
from typing import Optional
from src.components.rtc import RTC
from src.components.buzzer import Buzzer


class Alarms:
    """Gère les événements d'alarme du réveil."""

    def __init__(self, rtc: RTC, buzzer: Buzzer, audio_manager):
        self.rtc = rtc
        self.buzzer = buzzer
        self.audio_manager = audio_manager
        self.menu_manager = None  # Assigné dans menu_manager.py
        self.menu_manager: Optional["MenuManager"] = None
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
        self.triggered_times: dict[int, Optional[str]] = {
            1: None,
            2: None,
        }  # Marque la minute trigger par alarme
        self.active_alarm = None
        self.active_alarm_mode = None
        self.is_alarm_active = False
        self.music_playing = False  # Ajout pour cohérence
        self.last_stop_time = 0
        self.stop_cooldown = 60
        self.buzzer_timer = None
        self._load_alarms()

    def _load_alarms(self):
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
    ):
        """Règle une alarme."""
        self.alarm_states[alarm_num]["hour"] = hour
        self.alarm_states[alarm_num]["minute"] = minute
        self.alarm_states[alarm_num]["enabled"] = enabled
        self.alarm_states[alarm_num]["frequency"] = frequency
        self.rtc.set_alarm(alarm_num, hour, minute, enabled)

    def start_buzzer(self):
        """Active buzzer avec timeout 1 min."""
        self.buzzer.activate()
        self.buzzer_timer = time.time()
        self.audio_manager.music_playing = False  # Buzzer n'est pas musique
        self.active_alarm_mode = "buzzer"
        self.is_alarm_active = True

    def _check_buzzer_timeout(self):
        """Vérifie timeout buzzer (1 min)."""
        if self.buzzer_timer and time.time() - self.buzzer_timer >= 60:
            self.buzzer.stop()
            self.buzzer_timer = None
            self.is_alarm_active = False
            self.active_alarm = None
            self.active_alarm_mode = None
            if self.menu_manager:
                self.menu_manager._render()

    def check_alarms(self, current_time: str):
        """Vérifie si alarme due et déclenche (one-shot par minute)."""
        self._check_buzzer_timeout()
        if self.is_alarm_active:
            return
        current_hour, current_minute = map(int, current_time.split(":"))
        current_dow = self.rtc.read_dow()
        for alarm_num, state in self.alarm_states.items():
            if not state["enabled"]:
                continue
            if state["hour"] == current_hour and state["minute"] == current_minute:
                # Vérif one-shot : évite relance dans même minute
                if current_time == self.triggered_times.get(alarm_num):
                    continue
                freq = state["frequency"]
                trigger = False
                if freq == "T":
                    trigger = True
                elif freq == "S" and 1 <= current_dow <= 5:
                    trigger = True
                elif freq == "W" and current_dow in [6, 7]:
                    trigger = True
                if trigger:
                    self.triggered_times[alarm_num] = (
                        current_time  # Marque comme déclenché
                    )
                    self.active_alarm = alarm_num
                    self.is_alarm_active = True
                    self.active_alarm_mode = state.get("mode", "buzzer")
                    success = False
                if self.active_alarm_mode == "webradio":
                    index = state.get("station_index", 0)
                    success = self.audio_manager.play_webradio_station(index)
                    if not success:
                        time.sleep(2.0)  # Attente avant fallback SD
                        self.active_alarm_mode = "sd"
                        success = self.audio_manager.play_random_music()
                    else:
                        time.sleep(2.0)  # Délai pour stabiliser webradio
                        if self.menu_manager:
                            self.menu_manager.music_source = (
                                "webradio"  # Set pour parsing correct
                            )
                            self.menu_manager.current_station_name = (
                                self.menu_manager.webradio_stations[index]["name"]
                            )  # Set nom station pour affichage
                            self.menu_manager.music_start_time = (
                                time.time()
                            )  # Active délai 5s
                            self.music_playing = True
                elif self.active_alarm_mode == "sd":
                    success = self.audio_manager.play_random_music()
                    if success and self.menu_manager:
                        self.menu_manager.music_source = (
                            "sd"  # Set pour parsing correct
                        )
                        self.menu_manager.music_start_time = (
                            time.time()
                        )  # Active délai 5s
                        self.music_playing = True
                        if self.menu_manager:  # Vérif pour éviter AttributeError
                            self.menu_manager.music_start_time = (
                                time.time()
                            )  # Active délai 5s
                    else:
                        # Fallback buzzer si audio échoue (ou mode buzzer)
                        self.active_alarm_mode = "buzzer"
                        self.start_buzzer()
                    if self.menu_manager:
                        self.menu_manager._render()

    def stop(self) -> None:
        """Arrête l'alarme en cours."""
        if self.is_alarm_active:
            if self.active_alarm_mode in ["sd", "webradio"]:
                self.audio_manager.stop()
                self.music_playing = False
            elif self.active_alarm_mode == "buzzer":
                self.buzzer.stop()
            self.is_alarm_active = False
            self.active_alarm = None
            self.active_alarm_mode = None
            if self.menu_manager:
                self.menu_manager._render()

    def get_indicators(self):
        """Retourne indicateurs/frequences pour affichage."""
        indicators = (self.alarm_states[1]["enabled"], self.alarm_states[2]["enabled"])
        frequencies = (
            self.alarm_states[1]["frequency"],
            self.alarm_states[2]["frequency"],
        )
        return indicators, frequencies
