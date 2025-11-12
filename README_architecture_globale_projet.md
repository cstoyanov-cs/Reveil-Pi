# RÉVEIL RASPBERRY PI - DOCUMENTATION ARCHITECTURE
**Documentation technique optimisée pour compréhension IA**

---

## STRUCTURE RÉELLE DU PROJET

```
~/Documents/PROJETS/DEV/Reveil/code-p/
│
├── main.py                          # POINT D'ENTRÉE - Lance tout
├── webradios.json                   # Config stations (France Inter, Culture, FIP)
├── LICENSE
├── README.md
├── UPSHat_monitoring.py            # Monitoring batterie (non-essentiel)
│
├── src/
│   ├── config/
│   │   └── config.py               # CONFIG HARDWARE - Pins GPIO, I2C, timeouts
│   │
│   ├── coordinator/
│   │   └── coordinator.py          # ★ BOUCLE PRINCIPALE - Orchestration totale
│   │
│   └── components/
│       ├── __init__.py
│       │
│       ├── Hardware I/O:
│       │   ├── i2c.py              # Bus I2C (retry, recovery)
│       │   ├── rtc.py              # DS3231 (heure RTC, alarmes hardware)
│       │   ├── display.py          # SH1106 OLED (show_time, show_menu, show_settings)
│       │   ├── buzzer.py           # Piezo (thread beep loop)
│       │   └── rotary.py           # KY-040 (événements up/down/menu/long_press)
│       │
│       ├── Logique métier:
│       │   ├── time.py             # Gestion heure + DST
│       │   ├── alarms.py           # ★ Check alarmes + trigger (SD/Radio/Buzzer)
│       │   ├── audio_manager.py   # ★ MPD - Lecture SD/Webradio
│       │   └── controls.py         # Contrôles MPD (next/prev/pause/stop)
│       │
│       └── menu/                   # ★ SYSTÈME DE MENUS (21 fichiers)
│           ├── __init__.py
│           ├── base_menu.py        # Classe abstraite (handle_input, _render, blink)
│           ├── menu_manager.py     # ★ ORCHESTRATEUR - États globaux, transitions, params.json
│           │
│           ├── Navigation principale:
│           │   ├── main_menu.py                # 7 options racines
│           │   ├── settings_menu.py            # Paramètres système
│           │   └── set_param_menu.py           # Réglage valeur numérique générique
│           │
│           ├── Gestion temps:
│           │   ├── set_time_menu.py            # HH:MM (hour→minute)
│           │   └── set_date_menu.py            # view→dow→date→month→year
│           │
│           ├── Gestion alarmes (hiérarchie 4 niveaux):
│           │   ├── alarm_submenu.py            # Choix A1/A2
│           │   ├── alarm_config_menu.py        # Config A1/A2 (heure/freq/mode)
│           │   ├── set_alarm_menu.py           # Réglage HH:MM
│           │   ├── set_frequency_menu.py       # T/S/WE
│           │   ├── set_alarm_mode_menu.py      # SD/Radio/Buzzer
│           │   ├── set_webradio_station_menu.py # Choix station pour alarme
│           │   ├── alarm_activation_menu.py    # Toggle enabled (déprécié)
│           │   └── alarm_activation_switches.py # ★ Gestion switches GPIO24/25
│           │
│           └── Lecture audio:
│               ├── music_source_menu.py        # Choix SD/Webradio
│               ├── sd_card_menu.py             # Aléatoire / Parcourir
│               ├── sd_browser_menu.py          # ★ Navigateur fichiers récursif
│               ├── web_radio_menu.py           # Liste stations + contrôles live
│               ├── music_player_menu.py        # Contrôles lecture SD
│               └── playback_mode_menu.py       # Séquentiel/Aléatoire
│
└── tests_materiel/                 # Tests hardware isolés (non-utilisés runtime)
```

---

## FLUX D'EXÉCUTION - VISION IA

### 1. DÉMARRAGE (main.py)
```
GPIO.setmode(BCM) → Crée composants → Charge webradios.json → Lance MPD → coordinator.run()
```

**Composants créés (ordre important):**
```python
I2C(config) → RTC(i2c) → Display(i2c) → Buzzer(config) → Rotary(config)
AudioManager(music_dir, []) → Time(rtc) → Alarms(rtc, buzzer, audio)
MenuManager(display, time, alarms, audio) → Coordinator(tous_les_composants)
```

### 2. BOUCLE INFINIE (coordinator.py @ 50ms)

```
TANT QUE True:
    ┌─ 1. time_str = time_manager.get_time()           # Lit RTC
    ├─ 2. alarm_manager.check_alarms(time_str)         # ★ Trigger si match
    ├─ 3. events = rotary.get_events()                 # up/down/menu/long
    ├─ 4. menu_manager.handle_input(events, 0.5)       # ★ Délégation
    │     │
    │     └─ SI current_menu == None:
    │           ├─ menu short → _switch_to("MainMenu")
    │           ├─ menu long → audio_manager.stop()
    │           └─ up/down → controls.next()/prev() OU change_station()
    │        SINON:
    │           └─ current_menu.handle_input(events)
    │                 └─ Chaque menu gère sa logique + _switch_to() si transition
    │
    ├─ 5. SI audio_manager.music_playing:
    │       temp_info = audio_manager.get_formatted_track_info()  # Métadonnées MPD
    │
    ├─ 6. _handle_screen_saver(current_time)          # Power on/off selon activité
    │
    └─ 7. menu_manager._render()                       # Affiche temps/menu/infos
          │
          └─ SI temp_info: display.show_settings(temp_info)
             SINON SI current_menu: current_menu._render()
             SINON: display.show_time(time_str, indicators, frequencies, music_source)
    
    sleep(0.05)  # 50ms
```

---

## PATTERN CLÉS - CE QUE L'IA DOIT RETENIR

### A. GESTION DES MENUS (menu_manager.py)

**États globaux centralisés:**
```python
# Variables partagées entre TOUS les menus
current_menu: BaseMenu | None     # Menu actif (None = affichage temps)
selected_option: int              # Index option sélectionnée
alarm1/2_hour/minute/enabled/frequency/mode/station_index  # Configs alarmes
music_source: "sd" | "webradio" | None
current_station_index: int | None
temp_info: str | None             # Infos musique temporaires (15s)
settings: dict                    # screen_timeout, menu_timeout, playback_mode...
```

**Méthode critique: _switch_to()**
```python
def _switch_to(self, menu_class: str, **kwargs):
    """Change le menu actuel"""
    self.current_menu = menu_classes[menu_class](self, **kwargs)
    self.reset_activity()  # Allume écran, reset timer
    self._render()
```

**Sauvegarde persistante (params.json):**
```python
# Créé automatiquement dans /home/reveil/params.json au premier save_params()
{
  "settings": {...},               # De CONFIG["settings"] en config.py
  "alarm1_frequency": "T",
  "alarm1_mode": "sd",
  "alarm1_station_index": null,
  ... (idem alarm2)
}
```

### B. PATTERN MENU (base_menu.py → Tous les menus)

**Template commun:**
```python
class MonMenu(BaseMenu):
    def __init__(self, manager):
        super().__init__(manager)  # Récupère display, time_manager, alarm_manager
        self.options = ["Option1", "Option2"]
        self.manager.selected_option = 0
    
    def handle_input(self, events, blink_interval):
        for event in events:
            if event["button"] == "up" and event["type"] == "short_press":
                self.manager.selected_option = (self.manager.selected_option - 1) % len(self.options)
            elif event["button"] == "down":
                self.manager.selected_option = (self.manager.selected_option + 1) % len(self.options)
            elif event["button"] == "menu" and event["type"] == "short_press":
                # Logique validation option
                if self.manager.selected_option == 0:
                    self.manager._switch_to("AutreMenu", param=value)
            elif event["button"] == "menu" and event["type"] == "long_press":
                self.manager.current_menu = None  # Retour affichage temps
        self._render()
    
    def _render(self):
        self.display.show_menu(self.options, self.manager.selected_option)
```

### C. DÉCLENCHEMENT ALARME (alarms.py)

**One-shot par minute (évite re-trigger):**
```python
self.triggered_times = {1: None, 2: None}  # Stocke "HH:MM" dernière activation

def check_alarms(self, current_time: str):  # Appelé chaque 50ms par coordinator
    if current_time == self.triggered_times[alarm_num]:
        continue  # ✅ Déjà sonnée cette minute
    
    # Vérifie heure + fréquence (T/S/WE) + jour semaine
    if trigger:
        self.triggered_times[alarm_num] = current_time  # Marque comme déclenchée
        
        if mode == "sd":
            audio_manager.play_random_music()
        elif mode == "webradio":
            audio_manager.play_webradio_station(index)
            if fail: fallback SD → fallback Buzzer
        elif mode == "buzzer":
            buzzer.activate()  # Thread bip 60s
```

### D. AUDIO (audio_manager.py + MPD)

**Modes:**
- **SD aléatoire**: `mpc clear; mpc random on; mpc add /; mpc play`
- **SD séquentiel**: Liste fichiers triés (tri naturel), add un par un, `mpc repeat off`
- **Webradio**: `mpc clear; mpc add <URL>; mpc play` (timeout 2s buffer)

**Récupération métadonnées:**
```python
def get_formatted_track_info(self):
    if mode == "webradio":
        return f"Station: {self.current_station_name}"
    else:  # SD
        artist_title = check_output(["mpc", "current", "--format", "%artist% - %title%"])
        time = parse_from_mpc_status()  # "1:30 / 3:45"
        return f"Titre: {artist_title}\nPosition: {time}"
```

### E. SWITCHES HARDWARE (alarm_activation_switches.py)

**GPIO 24/25 en pull-up interne:**
```python
GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.add_event_detect(pin, GPIO.BOTH, callback=self._switch_callback, bouncetime=200)

def _switch_callback(channel):
    enabled = GPIO.input(channel) == GPIO.LOW  # LOW=ON, HIGH=OFF
    alarm_manager.alarm_states[alarm_num]["enabled"] = enabled
    rtc.set_alarm(alarm_num, hour, minute, enabled)  # ★ Écrit dans RTC hardware
    
    if enabled:
        menu_manager.show_temp_alarm(alarm_num)  # Affiche 5s heure → 2s confirmation
    else:
        alarm_manager.stop()  # Si sonnait
```

---

## DÉPENDANCES CRITIQUES

**Hardware:**
- `RPi.GPIO` → Rotary, Buzzer, Switches
- `smbus2` → I2C (RTC + Display)
- `luma.oled` → Display SH1106
- `subprocess` → MPD (mpc commands)

**Ordre init obligatoire:**
```
I2C → RTC/Display (dépendent I2C)
Alarms → Audio (pour triggers)
MenuManager → Alarms (pour alarm_manager reference circulaire)
Coordinator → Tous (pour orchestration)
```

---

## CAS D'USAGE TYPIQUES

### 1. USER ALLUME ALARME VIA SWITCH
```
Switch GPIO24 → LOW
  → _switch_callback()
    → alarm_states[1]["enabled"] = True
    → rtc.set_alarm(1, 7, 30, True)  # Écrit registres DS3231
    → show_temp_alarm(1)
      → _switch_to("AlarmActivationSwitchesMenu", alarm_number=1)
        → Affiche "07:30" pendant 5s
        → Affiche "A1 activé" pendant 2s
        → current_menu = None (retour heure)
```

### 2. ALARME SE DÉCLENCHE
```
07:30:00 → check_alarms("07:30")
  → Match A1 (mode=webradio, index=0)
    → audio_manager.play_webradio_station(0)
      → mpc clear; mpc add <FranceInter.mp3>; mpc play
      → sleep(2.0)  # Buffer réseau
      → menu_manager.music_source = "webradio"
      → menu_manager.current_station_name = "France Inter"
    → coordinator._render()
      → display.show_time(time, indicators, freqs, music_source="webradio")
        → Affiche icône radio + indicateur lecture
```

### 3. USER NAVIGUE DANS SD
```
MainMenu → "Lire la musique" (short press)
  → _switch_to("MusicSourceMenu")
    → Options: ["Carte SD", "Webradio", "Retour"]
    → Select "Carte SD" (short press)
      → _switch_to("SDCardMenu")
        → Options: ["Lecture aléatoire", "Parcourir", "Retour"]
        → Select "Parcourir"
          → _switch_to("SDBrowserMenu", current_path="/home/reveil/Musique")
            → _list_directory() → ["📁 Jazz", "📁 Rock", "🎵 song.mp3"]
            → Select "📁 Jazz"
              → _switch_to("SDBrowserMenu", current_path=".../Jazz")
                → Select "🎵 file.mp3"
                  → play_file_sequential(file, folder)
                    → mpc clear; mpc repeat off; mpc add fichiers triés; mpc play
                    → current_menu = None (lecture directe)
```

---

## VALEURS PAR DÉFAUT IMPORTANTES

**Timeouts (config.py → CONFIG["settings"]):**
- `screen_timeout`: 30s (veille écran si inactif)
- `menu_timeout`: 30s (ferme menu si inactif)
- `alarm_screen_on_time`: 3600s (1h écran allumé pendant alarme)
- `alarm_max_duration`: 7200s (2h stop auto alarme)
- `temp_info_timeout`: 15s (durée affichage infos musique avant retour heure)

**GPIO:**
- Rotary: CLK=17, DT=22, SW=27
- Buzzer: 23
- Switches: A1=24, A2=25

**I2C:**
- RTC DS3231: 0x68
- Display SH1106: 0x3C

**Boucle principale:** 50ms (20 FPS)

---

## PIÈGES À ÉVITER (pour IA)

1. **params.json n'existe PAS dans repo** → Créé runtime au premier `save_params()`
2. **RTC contient AUSSI les alarmes** → `rtc.set_alarm()` écrit dans DS3231 hardware
3. **Switches overrident TOUT** → Priorité absolue sur état alarmes
4. **MPD doit tourner AVANT** → `main.py` lance si absent avec timeout 5s
5. **Transitions menus = _switch_to()** → Jamais `self.current_menu = Menu(...)` direct
6. **triggered_times évite re-trigger** → Check minute exacte, pas intervalle
7. **coordinator appelle toujours handle_input** → Même sans events (pour blink/timeouts)

---

## GLOSSAIRE TECHNIQUE

- **RTC**: Real-Time Clock (DS3231) - Horloge hardware avec batterie
- **MPD**: Music Player Daemon - Serveur audio Unix
- **mpc**: Client CLI pour MPD
- **BCD**: Binary-Coded Decimal - Format RTC
- **KY-040**: Modèle encodeur rotatif
- **SH1106**: Contrôleur OLED (similaire SSD1306, mais 132x64 offset)
- **One-shot**: Trigger unique par minute (évite boucle infinie)
- **Debouncing**: Anti-rebond hardware (10ms rotation, 50ms switch)

---

**FIN - Document optimisé pour parsing IA**