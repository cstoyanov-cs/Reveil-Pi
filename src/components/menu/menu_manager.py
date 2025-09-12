import time
import json
import os
import subprocess
from src.components.display import Display
from src.components.time import Time
from src.components.alarms import Alarms
from src.components.audio_manager import AudioManager
from .main_menu import MainMenu
from .set_time_menu import SetTimeMenu
from .alarm_activation_switches import AlarmActivationSwitchesMenu
from .alarm_submenu import AlarmSubMenu
from .set_alarm_menu import SetAlarmMenu
from .alarm_activation_menu import AlarmActivationMenu
from .set_frequency_menu import SetFrequencyMenu
from .set_date_menu import SetDateMenu
from .settings_menu import SettingsMenu
from .set_param_menu import SetParamMenu
from .alarm_config_menu import AlarmConfigMenu
from .set_alarm_mode_menu import SetAlarmModeMenu
from .set_webradio_station_menu import SetWebradioStationMenu
from typing import Optional, Union, List, Dict, Any
from .music_source_menu import MusicSourceMenu
from .base_menu import BaseMenu

from src.config.config import CONFIG

PARAMS_FILE = "/home/reveil/params.json"  # Chemin persistant

menu_classes = {
    "MainMenu": MainMenu,
    "SetTimeMenu": SetTimeMenu,
    "AlarmSubMenu": AlarmSubMenu,
    "SetAlarmMenu": SetAlarmMenu,
    "AlarmActivationMenu": AlarmActivationMenu,
    "AlarmActivationSwitchesMenu": AlarmActivationSwitchesMenu,
    "SetFrequencyMenu": SetFrequencyMenu,
    "SetDateMenu": SetDateMenu,
    "SettingsMenu": SettingsMenu,
    "SetParamMenu": SetParamMenu,
    "AlarmConfigMenu": AlarmConfigMenu,
    "SetAlarmModeMenu": SetAlarmModeMenu,
    "SetWebradioStationMenu": SetWebradioStationMenu,
    "MusicSourceMenu": MusicSourceMenu,
}


class MenuManager:
    """Gère les menus du réveil et les états globaux."""

    MODE_NORMAL = 0  # Conservé pour cohérence, mais géré directement

    def __init__(
        self,
        display: Display,
        time_manager: Time,
        alarm_manager: Alarms,
        audio_manager: AudioManager,
    ):
        self.display = display
        self.time_manager = time_manager
        self.audio_manager = (
            audio_manager  # Définis l'attribut (paramètre déjà présent)
        )
        self.alarm_manager = alarm_manager
        self.alarm_manager.menu_manager = self
        self.switch_manager: BaseMenu = AlarmActivationSwitchesMenu(
            self
        )  # Annotation explicite
        self.current_menu: Optional[BaseMenu] = None  # Annotation explicite
        self.selected_option: int = 0
        self.setting_hour: int = 0
        self.setting_minute: int = 0
        self.setting_year: int = 2000
        self.setting_month: int = 1
        self.setting_date: int = 1
        self.setting_dow: int = 1
        self.alarm1_hour: int = 0
        self.alarm1_minute: int = 0
        self.alarm1_enabled: bool = False
        self.alarm1_frequency: str = "T"
        self.alarm1_mode: str = "sd"
        self.alarm1_station_index: Optional[int] = None
        self.alarm2_hour: int = 0
        self.alarm2_minute: int = 0
        self.alarm2_enabled: bool = False
        self.alarm2_frequency: str = "T"
        self.alarm2_mode: str = "sd"
        self.alarm2_station_index: Optional[int] = None
        self.time_initialized: bool = False
        self.date_initialized: bool = False
        self.last_update: float = time.time()
        self.update_interval: float = 1.0
        self.alarm_stopped_recently: bool = False
        self.alarm_stop_cooldown: float = 0.5
        self.last_alarm_stop_time: float = 0
        self.last_activity: float = time.time()
        self.settings: Dict[str, Union[bool, int]] = CONFIG[
            "settings"
        ].copy()  # Utilise CONFIG
        self.webradio_stations: List[Dict[str, str]] = self.load_webradios()
        self.music_source: Optional[str] = None
        self.current_station_index: Optional[int] = None
        self.current_station_name: Optional[str] = None
        self.temp_info: Optional[str] = None
        self.temp_display_start: Optional[float] = None
        self.coordinator: Optional[Any] = None  # Any si type inconnu
        self.show_time_after_timeout: bool = False  # Nouvelle variable pour timeout
        self.load_params()
        self._load_alarm_states()
        self._render()
        self.music_start_time = (
            None  # Pour rafraîchissement non-bloquant des infos musique
        )

    def load_params(self) -> None:
        """Charge params et freq alarmes depuis JSON."""
        if os.path.exists(PARAMS_FILE):
            with open(PARAMS_FILE, "r") as f:
                data = json.load(f)
                self.settings.update(data.get("settings", {}))
                self.alarm1_frequency = data.get("alarm1_frequency", "T")
                self.alarm2_frequency = data.get("alarm2_frequency", "T")
                self.alarm_manager.alarm_states[1]["frequency"] = self.alarm1_frequency
                self.alarm_manager.alarm_states[2]["frequency"] = self.alarm2_frequency
                self.alarm1_mode = data.get("alarm1_mode", "sd")
                self.alarm1_station_index = data.get("alarm1_station_index", None)
                self.alarm2_mode = data.get("alarm2_mode", "sd")
                self.alarm2_station_index = data.get("alarm2_station_index", None)
                self.alarm_manager.alarm_states[1]["mode"] = self.alarm1_mode
                self.alarm_manager.alarm_states[2]["mode"] = self.alarm2_mode
                self.alarm_manager.alarm_states[1]["station_index"] = (
                    self.alarm1_station_index
                )
                self.alarm_manager.alarm_states[2]["station_index"] = (
                    self.alarm2_station_index
                )

    def load_webradios(self):
        import json
        import os

        file_path = "/home/reveil/webradios.json"
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                data = json.load(f)
                return data.get("stations", [])
        return []

    def save_params(self) -> None:
        """Sauvegarde params et freq alarmes dans JSON."""
        data = {
            "settings": self.settings,
            "alarm1_frequency": self.alarm1_frequency,
            "alarm2_frequency": self.alarm2_frequency,
            "alarm1_mode": self.alarm1_mode,
            "alarm2_mode": self.alarm2_mode,
            "alarm1_station_index": self.alarm1_station_index,
            "alarm2_station_index": self.alarm2_station_index,
        }
        with open(PARAMS_FILE, "w") as f:
            json.dump(data, f)

    def reset_activity(self) -> None:
        """Reset timer activité, allume écran si off."""
        self.last_activity = time.time()
        self.display.power_on()

    def _load_alarm_states(self) -> None:
        self.alarm1_hour, self.alarm1_minute, self.alarm1_enabled = (
            self.alarm_manager.alarm_states[1]["hour"],
            self.alarm_manager.alarm_states[1]["minute"],
            self.alarm_manager.alarm_states[1]["enabled"],
        )
        self.alarm2_hour, self.alarm2_minute, self.alarm2_enabled = (
            self.alarm_manager.alarm_states[2]["hour"],
            self.alarm_manager.alarm_states[2]["minute"],
            self.alarm_manager.alarm_states[2]["enabled"],
        )
        self.alarm1_frequency = self.alarm_manager.alarm_states[1]["frequency"]
        self.alarm2_frequency = self.alarm_manager.alarm_states[2]["frequency"]
        self.alarm1_mode = self.alarm_manager.alarm_states[1].get("mode", "sd")
        self.alarm2_mode = self.alarm_manager.alarm_states[2].get("mode", "sd")
        self.alarm1_station_index = self.alarm_manager.alarm_states[1].get(
            "station_index", None
        )
        self.alarm2_station_index = self.alarm_manager.alarm_states[2].get(
            "station_index", None
        )

    def _switch_to(self, menu_class, **kwargs):
        self.current_menu = menu_classes[menu_class](self, **kwargs)
        self.reset_activity()  # Reset sur entrée menu
        self._render()

    def handle_input(self, events: List[Dict[str, str]], blink_interval: float) -> None:
        current_time = time.time()
        if self.current_menu is None:
            if current_time - self.last_update >= self.update_interval:
                self.last_update = current_time
                self._render()
            if current_time - self.last_activity > self.settings["menu_timeout"]:
                self.temp_info = None
                self.temp_display_start = None
                self.show_time_after_timeout = True  # Forcer affichage heure
                self._render()
            for event in events:
                button, event_type = event["button"], event["type"]
                if button == "menu" and event_type in ["short_press", "long_press"]:
                    if not self.display.is_on:  # Écran en veille
                        self.reset_activity()  # Réactive l'écran sans autre action
                        continue
                    if self.audio_manager.music_playing:
                        if not self.music_source:
                            continue  # Skip si source inconnue
                        if button == "menu" and event_type == "short_press":
                            if self.alarm_manager.is_alarm_active:
                                self.alarm_manager.stop()
                                self.alarm_stopped_recently = True
                                self.last_alarm_stop_time = current_time
                                self.music_source = None  # Réinitialiser source
                            else:
                                result = subprocess.run(
                                    ["mocp", "-G"],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                )
                                self.temp_info = self.get_current_music_info()
                                self.temp_display_start = current_time
                                self._render()
                        elif button == "menu" and event_type == "long_press":
                            self.current_station_name = None
                            self.current_station_index = None
                            self.audio_manager.stop()
                            self.music_source = None  # Réinitialiser source
                            self.current_menu = None  # Retour mode normal
                            self.alarm_stopped_recently = False
                            self._render()
                    else:
                        if (
                            self.alarm_manager.buzzer.active
                            or self.audio_manager.music_playing
                        ):
                            self.alarm_manager.stop()
                            self.alarm_stopped_recently = True
                            self.last_alarm_stop_time = current_time
                            self.music_source = None  # Réinitialiser source
                        elif not self.alarm_stopped_recently or (
                            current_time - self.last_alarm_stop_time
                            > self.alarm_stop_cooldown
                        ):
                            if self.display.is_on:
                                self._switch_to("MainMenu")
                                self.alarm_stopped_recently = False
                            self.reset_activity()
                elif (
                    button in ["up", "down"]
                    and event_type == "short_press"
                    and self.audio_manager.music_playing
                ):
                    if not self.music_source:
                        continue
                    if self.music_source == "sd":
                        cmd = ["mocp", "-f"] if button == "up" else ["mocp", "-r"]
                        result = subprocess.run(
                            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                        )
                        if result.stderr:
                            print(
                                f"[ERROR {current_time:.3f}] Erreur commande {cmd}, stderr={result.stderr.decode()}"
                            )
                        self.temp_info = self.get_current_music_info()
                        self.temp_display_start = current_time
                        self._render()
                    elif self.music_source == "webradio":
                        delta = 1 if button == "up" else -1
                        next_index = (
                            (
                                self.current_station_index
                                if self.current_station_index is not None
                                else 0
                            )
                            + delta
                        ) % len(self.webradio_stations)
                        self.current_station_index = next_index
                        self.current_station_name = self.webradio_stations[next_index][
                            "name"
                        ]
                        self.audio_manager.play_webradio_station(next_index)
                        self.temp_info = self.get_current_music_info()
                        self.temp_display_start = current_time
                        self._render()
                else:
                    self.reset_activity()
        else:
            assert self.current_menu is not None
            if events:
                self.reset_activity()
            self.current_menu.handle_input(events, blink_interval)
            if current_time - self.last_activity > self.settings["menu_timeout"]:
                self.current_menu = None
                self.reset_activity()

    def _render(self) -> None:
        current_time = time.time()
        if self.current_menu is not None:
            self.current_menu._render()
            return
        if self.show_time_after_timeout or not self.audio_manager.music_playing:
            self.temp_info = None
            self.temp_display_start = None
            time_str = self.time_manager.get_time()
            indicators, frequencies = self.alarm_manager.get_indicators()
            self.display.show_time(
                time_str,
                indicators,
                frequencies,
                playing=self.audio_manager.music_playing,
            )
        elif self.temp_display_start and current_time - self.temp_display_start < 3:
            temp_info = self.temp_info if self.temp_info is not None else "Inconnu"
            self.display.show_settings(temp_info, "", True)
        elif self.audio_manager.music_playing:
            self.temp_info = self.get_current_music_info()
            self.temp_display_start = current_time
            self.display.show_settings(self.temp_info, "", True)

    def show_temp_alarm(self, alarm_num: int) -> None:
        self._switch_to("AlarmActivationSwitchesMenu", alarm_number=alarm_num)

    def get_current_music_info(self) -> str:
        """Récupère titre ou station via MOCP avec délai initial et vérification d'état."""
        # Attendre 5s après démarrage musique pour laisser webradio se stabiliser
        if self.music_start_time and time.time() - self.music_start_time < 5.0:
            return "Chargement..."

        # Vérifie si MOC est en lecture
        try:
            result = subprocess.run(
                ["mocp", "-i"], capture_output=True, text=True, timeout=2.5, check=False
            )
            if result.returncode != 0 or "State: STOP" in result.stdout:
                return "Inconnu"
        except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
            print(f"[ERROR {time.time():.3f}] Erreur vérification état MOC: {e}")
            return "Inconnu"

        # Tente de récupérer les infos
        for _ in range(3):  # 3 tentatives sur ~1.5s
            try:
                output = (
                    subprocess.check_output(["mocp", "-i"], timeout=5.0)
                    .decode()
                    .strip()
                )
                lines = output.split("\n")
                info = {
                    line.split(": ", 1)[0]: line.split(": ", 1)[1]
                    for line in lines
                    if ": " in line
                }
                if self.music_source == "sd":
                    title = info.get("SongTitle", info.get("Title", "Inconnu"))
                    artist = info.get("Artist", "Inconnu")
                    result = (
                        f"Carte SD\nArtiste: {artist}\nTitre: {title}"
                        if artist != "Inconnu"
                        else f"Carte SD\nTitre: {title}"
                    )
                    return result

                elif self.music_source == "webradio":
                    station = self.current_station_name or "Inconnu"
                    title = info.get("SongTitle", info.get("Title", ""))
                    file_url = info.get("File", "")
                    if file_url:
                        file_basename = os.path.basename(
                            file_url
                        )  # Extrait nom fichier de URL
                        if title == file_basename or title.endswith(
                            (".mp3", ".m3u8", ".aac", ".ogg")
                        ):
                            title = "Inconnu"  # Filename par défaut → inconnu
                    result = f"Webradio\nStation: {station}\nTitre: {title}"
                    return result

            except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
                print(
                    f"[ERROR {time.time():.3f}] Échec tentative get_current_music_info: {e}"
                )
                time.sleep(0.5)  # Attente avant réessai
        print(
            f"[ERROR {time.time():.3f}] Échec get_current_music_info après 3 tentatives"
        )
        return "Inconnu"

    def play_webradio_station(self, index: int):
        if index >= len(self.webradio_stations):
            return
        self.audio_manager.play_webradio_station(index)
        self.current_station_index = index
        self.current_station_name = self.webradio_stations[index]["name"]
        self.music_source = "webradio"
