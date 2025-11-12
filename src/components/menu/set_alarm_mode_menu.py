from .base_menu import BaseMenu
from typing import List, Dict


class SetAlarmModeMenu(BaseMenu):
    def __init__(self, manager, alarm_number):
        super().__init__(manager)
        self.alarm_number = alarm_number
        self.options = ["Carte SD", "Webradio", "Buzzer", "Retour"]
        current_mode = self.manager.alarm_manager.alarm_states[self.alarm_number].get(
            "mode", "sd"
        )
        if current_mode == "sd":
            self.manager.selected_option = 0
        elif current_mode == "webradio":
            self.manager.selected_option = 1
        elif current_mode == "buzzer":
            self.manager.selected_option = 2
        else:
            self.manager.selected_option = 0

    def handle_input(self, events: List[Dict[str, str]], blink_interval: float) -> None:
        super().handle_input(
            events, blink_interval
        )  # Gère long_press (retour à l'heure)
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
                    self.manager._switch_to(
                        "AlarmConfigMenu", alarm_number=self.alarm_number
                    )
                elif selected == 0:  # Carte SD
                    self.manager.alarm_manager.alarm_states[self.alarm_number][
                        "mode"
                    ] = "sd"
                    self.manager.alarm_manager.alarm_states[self.alarm_number][
                        "station_index"
                    ] = None
                    if self.alarm_number == 1:
                        self.manager.alarm1_mode = "sd"
                        self.manager.alarm1_station_index = None
                    else:
                        self.manager.alarm2_mode = "sd"
                        self.manager.alarm2_station_index = None
                    self.manager._load_alarm_states()  # Synchronise
                    self.manager.save_params()
                    self.manager._switch_to(
                        "AlarmConfigMenu", alarm_number=self.alarm_number
                    )
                elif selected == 1:  # Webradio
                    self.manager._switch_to(
                        "SetWebradioStationMenu",
                        alarm_number=self.alarm_number,
                        mode="config",
                    )
                elif selected == 2:  # Buzzer
                    self.manager.alarm_manager.alarm_states[self.alarm_number][
                        "mode"
                    ] = "buzzer"
                    self.manager.alarm_manager.alarm_states[self.alarm_number][
                        "station_index"
                    ] = None
                    if self.alarm_number == 1:
                        self.manager.alarm1_mode = "buzzer"
                        self.manager.alarm1_station_index = None
                    else:
                        self.manager.alarm2_mode = "buzzer"
                        self.manager.alarm2_station_index = None
                    self.manager._load_alarm_states()  # Synchronise
                    self.manager.save_params()
                    self.manager._switch_to(
                        "AlarmConfigMenu", alarm_number=self.alarm_number
                    )
        if changed:
            self._render()

    def _render(self) -> None:
        self.display.show_menu(self.options, self.manager.selected_option)
