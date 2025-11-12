# Projet Réveil-Pi 🕰️

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)

## Description
Ce projet est un réveil numérique basé sur un Raspberry Pi 2. Il affiche l'heure en temps réel via un module RTC DS3231, gère deux alarmes configurables (heure, fréquence, mode), et joue de la musique depuis une carte SD ou des webradios via MPD (Music Player Daemon) pour les réveils, avec un buzzer de secours en cas de panne audio. L'interface repose sur un encodeur rotatif KY-040 pour naviguer dans des menus intuitifs sur un écran OLED SH1106. Le système est alimenté par un UPS HAT Waveshare pour une autonomie en cas de coupure.

Le code Python est modulaire : interruptions GPIO optimisées pour réactivité, cache heure pour minimiser les lectures RTC, mode veille pour économie d'énergie, et persistance des configs (alarms dans RTC, params dans JSON).

## Fonctionnalités Principales
- Affichage heure/date sur OLED avec indicateurs (fréquence alarmes, source musique).
- Deux alarmes indépendantes : configurable (HH:MM, T/S/WE, SD/Webradio/Buzzer) ; override hardware via switches.
- Lecture audio : aléatoire/séquentiel SD, webradios (ex. France Inter) ; métadonnées affichées 15s.
- Navigation : rotation (up/down), appui court (valider), long (retour/arrêt musique).
- Persistance : alarmes stockées dans RTC (survie redémarrage) ; params système en `/home/pi/params.json`.
- Veille : écran off après 30s inactivité ; réactivé par interaction.
- Surveillance UPS : monitoring batterie (optionnel via script dédié).

## Matériel Requis
| **Raspberry Pi 2** | Micro-ordinateur principal.
| **Écran OLED SH1106** | 128x64 pixels monochrome.
| **RTC DS3231** | Horloge temps réel avec pile.
| **Buzzer** | Mode d'alarme de secours si mpd est en erreur.
| **Encodeur rotatif cliquable KY-040** | Navigation UI. |
| **Raspberry DAC Pro** | Sortie audio. |
| **Amplificateur PAM8406** | Stéréo 3W/canal. | - |
| **Enceintes stéréo 3W 8Ω** | x2 haut-parleurs. | - |
| **Waveshare Pi Hat UPS** | Alim 5V/5A avec 2x 18650.
| **Interrupteurs ON/OFF** | Switches (x2) pour l'activation ou désactivation des deux alarmes.

**Notes** : Jumpers MF pour KY-040/switches ; activez I2C via `raspi-config`. Boîtier DIY recommandé.

## Prérequis Logiciels
- Raspberry Pi OS Lite (basé Debian).
- Python 3.8+ avec libs :
  ```bash
  pip install smbus2 RPi.GPIO luma.oled pillow
  ```
- MPD pour audio :
  ```bash
  sudo apt update && sudo apt install mpd mpc
  ```
- Activez I2C : `sudo raspi-config` > Interface Options > I2C > Yes.

## Installation
1. Clonez le repo :
   ```bash
   git clone https://github.com/cstoyanov-cs/Reveil-Pi.git
   cd Reveil-Pi
   ```
2. Installez dépendances (voir ci-dessus).
3. Configurez MPD : Éditez `/etc/mpd.conf` pour socket local (`music_directory "/home/pi/Music"` ; ajoutez webradios dans `webradios.json`).
4. Lancez :
   ```bash
   python main.py
   ```
5. Auto-démarrage : Créez un systemd service (ex. `/etc/systemd/system/reveil.service` avec `ExecStart=/usr/bin/python /path/to/main.py` ; `sudo systemctl enable reveil`).

## Utilisation
- **Démarrage** : Affiche l'heure. Appui court sur encodeur → menu principal.
- **Menus hiérarchiques** :
  - **Réglage alarme** : Choisir A1/A2 → heure (HH:MM) → fréquence (T/S/WE) → mode (SD/Webradio/Buzzer) → station webradio.
  - **Lire musique** : SD (aléatoire/parcourir) ou Webradio → sélection + contrôles (next/prev/pause).
  - **Réglages** : Timeout écran/menu, synchroniser heure RTC.
  - Retour : Appui long ou "Retour".
- **Alarmes** : Déclenche à l'heure (check/minute). Stop par appui. Switches priorisent (override software).
- **Veille** : Écran off 30s ; buzzer/Music allume temporairement.

## Architecture Globale
Le code est modulaire (`src/` : config, coordinator, components). Flux principal :
1. **Init** (`main.py`) : GPIO/I2C → RTC/Display/Buzzer/Rotary → Time/Alarms/Audio → MenuManager → Coordinator.
2. **Boucle (`coordinator.py`) : Lit RTC → check alarmes → events rotary → handle menu → render (heure/menu/infos) → veille.
3. **Menus** : Centralisés via `MenuManager` (états globaux, transitions `_switch_to()`) ; chaque menu hérite `BaseMenu` (handle_input/render).
4. **Audio** : MPD via `mpc` (SD aléatoire : `random on` ; webradio : add URL + buffer 2s).
5. **Persistance** : Alarmes en registres RTC ; settings en JSON.

Structure arborescente :
```
Reveil-Pi/
├── main.py          # Entrée
├── webradios.json   # Stations (ex. France Inter)
├── src/
│   ├── config/config.py     # Pins/timeouts
│   ├── coordinator/coordinator.py  # Boucle
│   └── components/          # I/O (i2c.py, rtc.py...), métier (alarms.py, audio_manager.py), menu/ (21 fichiers hiérarchiques)
```

## Contribution
Forkez, modifiez (respectez patterns menus/alarms), testez sur Pi, PR avec description. Bugs ? Ouvrez une issue.

## Licence
MIT – Utilisez librement, citez la source.
