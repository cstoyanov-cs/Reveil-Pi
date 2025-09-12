import time
from .base_menu import BaseMenu
from typing import List, Dict


class SetWebradioStationMenu(BaseMenu):
    def __init__(self, manager, alarm_number=None, mode="config"):
        super().__init__(manager)
        self.alarm_number = alarm_number
        self.mode = mode
        self.options = [
            station["name"] for station in self.manager.webradio_stations
        ] + ["Retour"]
        if not self.manager.webradio_stations:
            self.options = ["Pas de stations webradio", "Retour"]
            self.manager.selected_option = 0
        else:
            if mode == "config" and alarm_number:
                current_index = self.manager.alarm_manager.alarm_states[
                    self.alarm_number
                ].get("station_index")
                self.manager.selected_option = (
                    current_index if current_index is not None else 0
                )
            else:
                self.manager.selected_option = self.manager.current_station_index or 0
        self._render()

    def play_station(self, index: int) -> bool:
        if index >= len(self.manager.webradio_stations):
            return False
        try:
            if self.manager.audio_manager.play_webradio_station(index):
                self.manager.current_station_index = index
                self.manager.current_station_name = self.manager.webradio_stations[
                    index
                ]["name"]
                self.manager.music_source = "webradio"
                return True
            return False
        except Exception:
            return False

    def handle_input(self, events: List[Dict[str, str]], blink_interval: float) -> None:
        super().handle_input(events, blink_interval)
        self._update_blink(blink_interval)
        changed = False
        for event in events:
            button = event["button"]
            event_type = event["type"]
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
                selected = self.manager.selected_option
                if selected == len(self.options) - 1:  # Retour
                    if self.mode == "config":
                        self.manager._switch_to(
                            "SetAlarmModeMenu", alarm_number=self.alarm_number
                        )
                    else:
                        self.manager._switch_to("MainMenu")
                elif not self.manager.webradio_stations:
                    return
                else:
                    index = selected
                    if self.mode == "config":
                        self.manager.alarm_manager.alarm_states[self.alarm_number][
                            "mode"
                        ] = "webradio"
                        self.manager.alarm_manager.alarm_states[self.alarm_number][
                            "station_index"
                        ] = index
                        if self.alarm_number == 1:
                            self.manager.alarm1_mode = "webradio"
                            self.manager.alarm1_station_index = index
                        else:
                            self.manager.alarm2_mode = "webradio"
                            self.manager.alarm2_station_index = index
                        self.manager._load_alarm_states()
                        self.manager.save_params()
                        self.manager._switch_to(
                            "AlarmConfigMenu", alarm_number=self.alarm_number
                        )
                    else:
                        index = selected
                        self.play_station(index)
                        self.manager.music_start_time = (
                            time.time()
                        )  # Marque début pour rafraîchissement non-bloquant
                        if self.alarm_manager.active_alarm:
                            self.manager.alarm_manager.alarm_states[
                                self.alarm_manager.active_alarm
                            ]["station_index"] = index
                        self.manager.temp_info = (
                            self.manager.get_current_music_info()
                        )  # Précharge
                        self.manager.temp_display_start = time.time()
                        self.manager.current_menu = None  # Retour à normal
                        self.manager._render()  # Force affichage
        if changed:
            self._render()

    def _render(self) -> None:
        self.display.show_menu(self.options, self.manager.selected_option)
