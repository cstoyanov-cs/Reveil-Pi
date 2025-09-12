import time
from src.components.time import Time
from src.components.alarms import Alarms
from src.components.menu.menu_manager import MenuManager
from src.components.rotary import RotaryEncoder
from src.components.display import Display
from src.components.audio_manager import AudioManager
from typing import Optional


class Coordinator:
    """Orchestre les composants du réveil."""

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
        self.menu_manager.coordinator = self
        self.rotary = rotary
        self.display = display
        self.config = config
        self.audio_manager = audio_manager
        self.loop_delay = config["general"]["main_loop_delay"]
        self.alarm_screen_timer = None

    def reset_activity(self) -> None:
        self.menu_manager.last_activity = time.time()
        self.display.power_on()

    def _handle_screen_saver(self, current_time: float) -> None:
        """Gère l'économiseur d'écran et timers d'alarme."""
        if not self.menu_manager.settings["screen_saver_enabled"]:
            return

        if self.menu_manager.current_menu is None:
            if (
                current_time - self.menu_manager.last_activity
                > self.menu_manager.settings["screen_timeout"]
            ):
                self.display.power_off()
                if self.audio_manager.music_playing:
                    self.menu_manager.temp_info = None
                    self.menu_manager.temp_display_start = None
                return

        if self.audio_manager.music_playing or self.alarm_manager.buzzer.active:
            if self.alarm_screen_timer is None:
                self.alarm_screen_timer = current_time
                self.display.power_on()
            elif (
                current_time - self.alarm_screen_timer
                > self.menu_manager.settings["alarm_screen_on_time"]
            ):
                self.alarm_screen_timer = None
        else:
            self.alarm_screen_timer = None

    def run(self) -> None:
        """Orchestre la boucle principale du réveil."""
        try:
            last_temp_info = None  # Dernière info musique pour éviter rendus redondants
            last_info_check = 0  # Dernière vérif de get_current_music_info
            render_needed = False  # Indicateur pour regrouper les rendus

            while True:
                current_time = time.time()
                time_str = self.time_manager.get_time()

                # Vérifie alarmes
                self.alarm_manager.check_alarms(time_str)

                # Traite inputs
                events = self.rotary.get_events()
                self.menu_manager.handle_input(
                    events, self.config["display"]["blink_interval"]
                )

                # Met à jour infos musique si nécessaire (limité à 1/s)
                if (
                    self.audio_manager.music_playing
                    and current_time - last_info_check >= 1.0
                ):
                    new_temp_info = self._update_music_info(last_temp_info)
                    last_info_check = current_time
                    if new_temp_info != last_temp_info:
                        self.menu_manager.temp_info = new_temp_info
                        self.menu_manager.temp_display_start = current_time
                        last_temp_info = new_temp_info
                        render_needed = True
                    if (
                        self.menu_manager.music_start_time
                        and self.menu_manager.temp_info is not None
                        and (
                            "Titre" in self.menu_manager.temp_info
                            or "Station" in self.menu_manager.temp_info
                        )
                    ):
                        self.menu_manager.music_start_time = None  # Stop vérif initiale

                # Gère économiseur d'écran
                self._handle_screen_saver(current_time)
                if self.menu_manager.settings["screen_saver_enabled"]:
                    render_needed = True  # Forcer rendu si écran réveillé

                # Rendu unique si nécessaire
                if render_needed or self.menu_manager.current_menu is not None:
                    self.menu_manager._render()
                render_needed = False

                time.sleep(self.loop_delay)

        except Exception as e:
            print(f"[ERROR {time.time():.3f}] Erreur coordinateur : {e}")
            if self.display.device:
                self.display.show_time("Erreur", (False, False), ("", ""))

    def _update_music_info(self, last_temp_info: Optional[str]) -> Optional[str]:
        """Met à jour infos musique si changement, retourne nouvelle info."""
        new_temp_info = self.menu_manager.get_current_music_info()
        if new_temp_info == last_temp_info or new_temp_info == "Chargement...":
            return new_temp_info
        return new_temp_info
