import json
import subprocess
import time
import os
from .base_menu import BaseMenu

WEBRADIOS_FILE = "/home/reveil/webradios.json"


class WebRadioMenu(BaseMenu):
    def __init__(self, manager):
        super().__init__(manager)
        self.stations = self.load_stations()
        self.options = [station["name"] for station in self.stations] + ["Retour"]
        self.manager.selected_option = 0
        self.current_station_index = None
        self.last_info_time = 0
        self.current_info = "Chargement..."

    def load_stations(self):
        if not os.path.exists(WEBRADIOS_FILE):
            return []  # Ou erreur
        with open(WEBRADIOS_FILE, "r") as f:
            data = json.load(f)
        return data.get("stations", [])

    def play_station(self, index):
        if index >= len(self.stations):
            return
        url = self.stations[index]["url"]
        subprocess.Popen(
            ["pkill", "-f", "mocp"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        time.sleep(0.05)  # Court délai pour pkill

        # Démarrer le serveur MOCP
        subprocess.Popen(["mocp", "-S"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(0.2)  # Délai pour laisser le serveur démarrer
        subprocess.Popen(
            ["mocp", "-a", url], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        subprocess.Popen(["mocp", "-p"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.manager.music_source = "webradio"
        self.current_station_index = index
        self.manager.current_station_name = self.stations[index]["name"]
        self.manager.alarm_manager.music_playing = True  # Pour tracking global

    def get_current_info(self):
        if self.current_station_index is None:
            return "Webradio\nStation: Inconnu\nTitre: Inconnu\n00:00/Streaming"
        try:
            output = subprocess.check_output(["mocp", "-i"]).decode().strip()
            lines = output.split("\n")
            info = {
                line.split(": ", 1)[0]: line.split(": ", 1)[1]
                for line in lines
                if ": " in line
            }
            title = info.get("SongTitle", info.get("Title", "Inconnu"))
            current = info.get("CurrentTime", "00:00")
            total = info.get("TotalTime", "Streaming")
            return f"Webradio\nStation: {self.stations[self.current_station_index]['name']}\nTitre: {title}\n{current}/{total}"
        except Exception:
            return "Webradio\nStation: Inconnu\nTitre: Inconnu\n00:00/Streaming"

    def handle_input(self, events: list[dict], blink_interval: float) -> None:
        _ = blink_interval
        current_time = time.time()
        changed = False
        for event in events:
            button, event_type = event["button"], event["type"]
            if self.current_station_index is not None:  # Pendant lecture
                if button == "up" and event_type == "short_press":
                    next_index = (self.current_station_index + 1) % len(self.stations)
                    self.manager.current_station_name = self.stations[next_index][
                        "name"
                    ]
                    self.play_station(next_index)
                    changed = True
                    self.manager.current_station_index = next_index
                elif button == "down" and event_type == "short_press":
                    prev_index = (self.current_station_index - 1) % len(self.stations)
                    self.manager.current_station_name = self.stations[prev_index][
                        "name"
                    ]
                    self.play_station(prev_index)
                    changed = True
                    self.manager.current_station_index = prev_index

                elif button == "menu" and event_type == "short_press":
                    self.manager._switch_to("MainMenu")  # Sans stop
                elif button == "menu" and event_type == "long_press":
                    self.manager.alarm_manager.stop()
                    self.manager.current_station_index = None
                    self.manager.current_menu = None
                    self.manager.music_source = None
            else:  # Sélection station
                if button == "up" and event_type == "short_press":
                    self.manager.selected_option = (
                        self.manager.selected_option - 1
                    ) % len(self.options)
                    changed = True
                elif button == "down" and event_type == "short_press":
                    self.manager.selected_option = (
                        self.manager.selected_option + 1
                    ) % len(self.options)
                    changed = True
                elif button == "menu" and event_type == "short_press":
                    if self.manager.selected_option < len(self.stations):
                        self.play_station(self.manager.selected_option)
                        changed = True
                    else:
                        self.manager._switch_to("MusicSourceMenu")

        if (
            self.current_station_index is not None
            and current_time - self.last_info_time >= 1
        ):
            self.current_info = self.get_current_info()
            self.last_info_time = current_time
            changed = True

        if changed:
            self._render()

    def _render(self) -> None:
        if self.current_station_index is not None:
            self.display.show_settings(self.current_info, None, True)
        else:
            self.display.show_menu(self.options, self.manager.selected_option)
