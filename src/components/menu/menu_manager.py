import time
import json
import os
from typing import Optional, Union, List, Dict, Any

# Importation des classes de menu
from .music_source_menu import MusicSourceMenu
from .sd_card_menu import SDCardMenu
from .sd_browser_menu import SDBrowserMenu
from .playback_mode_menu import PlaybackModeMenu
from ..display import Display
from ..time import Time
from ..alarms import Alarms
from ..audio_manager import AudioManager
from ..controls import MusicControls
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
from .restart_menu import RestartMenu
from .ssh_menu import SSHMenu
from .base_menu import BaseMenu
from src.config.config import CONFIG

PARAMS_FILE = "/home/reveil/params.json"  # Chemin persistant pour les paramètres

# Dictionnaire des classes de menu pour une gestion dynamique
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
    "RestartMenu": RestartMenu,
    "SSHMenu": SSHMenu,
    "MusicSourceMenu": MusicSourceMenu,
    "SDCardMenu": SDCardMenu,
    "SDBrowserMenu": SDBrowserMenu,
    "PlaybackModeMenu": PlaybackModeMenu,
}


class MenuManager:
    """Gère les menus du réveil et les états globaux."""

    def __init__(
        self,
        display: Display,
        time_manager: Time,
        alarm_manager: Alarms,
        audio_manager: AudioManager,
    ):
        self.display = display
        self.time_manager = time_manager
        self.audio_manager = audio_manager
        self.controls = MusicControls(audio_manager)
        self.alarm_manager = alarm_manager
        self.alarm_manager.menu_manager = self
        self.switch_manager: BaseMenu = AlarmActivationSwitchesMenu(self)
        self.current_menu: Optional[BaseMenu] = None  # Menu actuel
        self.selected_option: int = 0  # Option sélectionnée dans le menu actuel
        # Paramètres des alarmes
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
        self.last_update: float = time.time()  # Dernière mise à jour de l'affichage
        self.update_interval: float = 1.0  # Intervalle de mise à jour
        self.alarm_stopped_recently: bool = (
            False  # Flag pour éviter les actions répétées après un arrêt d'alarme
        )
        self.alarm_stop_cooldown: float = (
            0.5  # Délai de refroidissement après un arrêt d'alarme
        )
        self.last_alarm_stop_time: float = 0  # Dernier arrêt d'alarme
        self.last_activity: float = time.time()  # Dernière activité utilisateur
        self.settings: Dict[str, Union[bool, int]] = CONFIG[
            "settings"
        ].copy()  # Paramètres de configuration
        self.config = CONFIG  # Référence globale à la config pour timeouts
        self.webradio_stations: List[Dict[str, str]] = (
            self.load_webradios()
        )  # Liste des stations de radio
        self.music_source: Optional[str] = None  # Source musicale actuelle
        self.current_station_index: Optional[int] = None  # Index de la station actuelle
        self.current_station_name: Optional[str] = None  # Nom de la station actuelle
        self.temp_info: Union[Dict[str, Any], str, None] = (
            None  #  Accepte dict, str ou None
        )
        self.temp_display_start: Optional[float] = (
            None  # Heure de début d'affichage temporaire
        )
        self.coordinator: Optional[Any] = (
            None  # Référence au coordinateur (si nécessaire)
        )
        self.show_time_after_timeout: bool = (
            False  # Flag pour afficher l'heure après un timeout
        )
        self.music_start_time: Optional[float] = (
            None  # Heure de début de la lecture musicale
        )
        self.last_music_info_time = 0  # Dernière mise à jour des infos musicales
        self.last_music_info = None  # Dernières infos musicales
        self.last_rendered_state = None  # Ajout dirty flag
        self.screen_just_woken = False  #  NOUVEAU : Flag réveil écran
        self.load_params()  # Charge les paramètres sauvegardés
        self._load_alarm_states()  # Charge les états des alarmes
        self.mpd_unavailable = self.audio_manager.mpd_unavailable  # Sync flag MPD down
        self._render()  # Affiche l'interface initiale

    def load_params(self) -> None:
        """Charge les paramètres et les fréquences des alarmes depuis un fichier JSON."""
        try:
            if os.path.exists(PARAMS_FILE):
                with open(PARAMS_FILE, "r") as f:
                    data = json.load(f)
                    self.settings.update(data.get("settings", {}))
                    self.alarm1_frequency = data.get("alarm1_frequency", "T")
                    self.alarm2_frequency = data.get("alarm2_frequency", "T")
                    self.alarm_manager.alarm_states[1]["frequency"] = (
                        self.alarm1_frequency
                    )
                    self.alarm_manager.alarm_states[2]["frequency"] = (
                        self.alarm2_frequency
                    )
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
        except Exception as e:
            print(f"Erreur lors du chargement des paramètres: {e}")

    def load_webradios(self):
        """Charge la liste des stations de radio depuis un fichier JSON."""
        try:
            file_path = "/home/reveil/webradios.json"
            if os.path.exists(file_path):
                with open(file_path, "r") as f:
                    data = json.load(f)
                    return data.get("stations", [])
        except Exception as e:
            print(f"Erreur lors du chargement des stations de radio: {e}")
        return []

    def save_params(self) -> None:
        """Sauvegarde les paramètres et les fréquences des alarmes dans un fichier JSON."""
        try:
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
        except Exception as e:
            print(f"Erreur lors de la sauvegarde des paramètres: {e}")

    def reset_activity(self) -> None:
        """Réinitialise le timer d'activité et allume l'écran si nécessaire."""
        self.last_activity = time.time()
        self.display.power_on()

    def _load_alarm_states(self) -> None:
        """Charge les états des alarmes depuis le gestionnaire d'alarmes."""
        try:
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
        except Exception as e:
            print(f"Erreur lors du chargement des états des alarmes: {e}")

    def _switch_to(self, menu_class, **kwargs):
        """Passe à un nouveau menu."""
        try:
            self.current_menu = menu_classes[menu_class](self, **kwargs)
            self.reset_activity()  # Réinitialise l'activité
            self._render()  # Rafraîchit l'affichage
        except Exception as e:
            print(f"Erreur lors du changement de menu: {e}")

    def handle_input(self, events: List[Dict[str, str]], blink_interval: float) -> None:
        """Gère les événements d'entrée utilisateur avec corrections."""
        try:
            current_time = time.time()
            if self.current_menu is None:
                # ===== MODE NORMAL (pas de menu ouvert) =====
                if current_time - self.last_update >= self.update_interval:
                    self.last_update = current_time
                    self._render()
                # Timeout affichage infos musique
                if current_time - self.last_activity > self.settings["menu_timeout"]:
                    self.temp_info = None
                    self.temp_display_start = None
                    self.show_time_after_timeout = True
                    self._render()

                #  NOUVEAU : Gestion réveil centralisée (avant traitement events)
                was_off = False
                if events:  # Tout event → réveil potentiel
                    was_off = not self.display.is_on
                    self.reset_activity()  # Allume si off
                    if was_off:
                        self.screen_just_woken = True

                for event in events:
                    button, event_type = event["button"], event["type"]
                    #  Reset flag sur up/down (permet navigation immédiate après réveil)
                    if button in ["up", "down"]:
                        self.screen_just_woken = False

                    if button == "menu" and event_type in ["short_press", "long_press"]:
                        #  Skip si premier appui après veille (réveil seulement)
                        if self.screen_just_woken:
                            self.screen_just_woken = False
                            continue

                        if self.audio_manager.music_playing:
                            if not self.music_source:
                                continue
                            if event_type == "short_press":
                                if self.alarm_manager.is_alarm_active:
                                    self.alarm_manager.stop()
                                    self.alarm_stopped_recently = True
                                    self.last_alarm_stop_time = current_time
                                    self.music_source = None
                                else:
                                    self.controls.pause_toggle()
                                    self.temp_info = self.get_current_music_info()
                                    self.temp_display_start = current_time
                                    self._render()
                            elif event_type == "long_press":
                                self.current_station_name = None
                                self.current_station_index = None
                                self.audio_manager.stop()
                                self.music_source = None
                                self.current_menu = None
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
                                self.music_source = None
                            elif not self.alarm_stopped_recently or (
                                current_time - self.last_alarm_stop_time
                                > self.alarm_stop_cooldown
                            ):
                                # Ouvre menu (seul si pas juste réveillé)
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
                            success = (
                                self.controls.prev_track()
                                if button == "up"
                                else self.controls.next_track()
                            )
                            if success:
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
                            self.current_station_name = self.webradio_stations[
                                next_index
                            ]["name"]
                            self.audio_manager.play_webradio_station(next_index)
                            self.temp_info = self.get_current_music_info()
                            self.temp_display_start = current_time
                            self._render()
                    else:
                        self.reset_activity()
            else:
                # ===== MENU OUVERT ===== (inchangé)
                if events:
                    self.reset_activity()
                for event in events:
                    if event["button"] == "menu" and event["type"] == "long_press":
                        self.current_menu = None
                        self.reset_activity()
                        self._render()
                        return
                self.current_menu.handle_input(events, blink_interval)
                if current_time - self.last_activity > self.settings["menu_timeout"]:
                    print(
                        f"[TIMEOUT] Menu fermé après {self.settings['menu_timeout']}s"
                    )
                    self.current_menu = None
                    self.reset_activity()
                    self._render()  # Permet l'affichage de l'heure immédiate lorsqu'un menu reste ouvert
        except Exception as e:
            print(f"Erreur lors de la gestion des événements: {e}")

    def _render(self) -> None:
        """Rafraîchit l'affichage en fonction de l'état actuel."""
        time_str = (
            self.time_manager.get_time()
        )  # Ligne 1: Calcul heure en premier (pour dirty flag)
        try:  # Ligne 3: Début try (englobe tout)
            # Calcule hash état actuel
            current_state = (  # Lignes 5-11: Tuple dirty flag (inchangé)
                self.current_menu.__class__.__name__ if self.current_menu else None,
                str(self.temp_info) if self.temp_info else None,  # Stringify dict/str
                self.audio_manager.music_playing,
                tuple(self.alarm_manager.get_indicators()[0]),
                self.mpd_unavailable,
                time_str,
            )
            # ✅ Skip render si identique
            if current_state == self.last_rendered_state:  # Lignes 13-14
                return
            self.last_rendered_state = current_state  # Ligne 16

            # Ligne 18: Reset centralisé temp_info AVANT check musique (clé pour fixer la boucle)
            current_time = time.time()
            if (
                self.temp_display_start is not None
                and self.temp_info is not None
                and current_time - self.temp_display_start
                > self.settings.get("temp_info_timeout", 15)
            ):
                self.temp_info = None  # Reset infos musique après 15s
                self.temp_display_start = None

                # Affichage musique avec nouvel UI (seulement si pas reset):with expression as target:
                pass
            if (
                self.audio_manager.music_playing and self.temp_info is not None
            ):  # Ligne 30
                if isinstance(self.temp_info, dict):
                    # Nouveau format détaillé
                    self.display.show_music_player(
                        artist=self.temp_info.get("artist", "Inconnu"),
                        title=self.temp_info.get("title", "Inconnu"),
                        elapsed=self.temp_info.get("elapsed", "0:00"),
                        total=self.temp_info.get("total", "0:00"),
                        progress=self.temp_info.get("progress", 0.0),
                        is_playing=self.temp_info.get("is_playing", False),
                        source=self.temp_info.get("source", "sd"),
                    )
                else:
                    # Ancien format (fallback)
                    self.display.show_settings(self.temp_info, "", True)
                return  # Ligne 45: Retour après musique

            # Si un menu est ouvert, affiche-le
            if self.current_menu is not None:  # Ligne 48
                self.current_menu._render()
                return

            # Affichage temps principal avec indicateurs (Ligne 52: Utilise time_str existant, pas de recalcul)
            indicators, frequencies = self.alarm_manager.get_indicators()
            music_source = (
                self.music_source if self.audio_manager.music_playing else None
            )
            self.display.show_time(
                time_str,  # Utilise le time_str du début (économise 1 appel RTC)
                indicators,
                frequencies,
                playing=self.audio_manager.music_playing,
                music_source=music_source,
                mpd_unavailable=self.mpd_unavailable,
            )

            # Reset flag après affichage temps
            if self.show_time_after_timeout:  # Ligne 66
                self.show_time_after_timeout = False

        except Exception as e:  # Ligne 69: Except aligne avec try (couvre tout)
            print(f"Erreur lors du rafraîchissement de l'affichage: {e}")

    def show_temp_alarm(self, alarm_num: int) -> None:
        """Affiche temporairement le menu d'activation/désactivation de l'alarme."""
        try:
            self._switch_to("AlarmActivationSwitchesMenu", alarm_number=alarm_num)
        except Exception as e:
            print(f"Erreur lors de l'affichage temporaire du menu d'alarme: {e}")

    def get_current_music_info(self) -> Union[Dict[str, Any], str]:
        """
        Retourne les informations détaillées sur la musique en cours de lecture.

        Returns:
            dict avec infos détaillées ou str "Inconnu" en cas d'erreur
        """
        try:
            return self.audio_manager.get_detailed_track_info()
        except Exception as e:
            print(f"Erreur lors de la récupération des infos musicales: {e}")
            # Retourne un dict valide en cas d'erreur (pas juste "Erreur")
            return {
                "artist": "Erreur",
                "title": "Erreur",
                "elapsed": "0:00",
                "total": "0:00",
                "progress": 0.0,
                "is_playing": False,
                "source": None,
            }

    def play_webradio_station(self, index: int):
        """Joue une station de radio spécifique."""
        try:
            if index >= len(self.webradio_stations):
                return
            self.audio_manager.play_webradio_station(index)
            self.current_station_index = index
            self.current_station_name = self.webradio_stations[index]["name"]
            self.music_source = "webradio"
        except Exception as e:
            print(f"Erreur lors de la lecture de la station webradio: {e}")
