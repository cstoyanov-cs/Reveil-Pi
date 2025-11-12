"""
Configuration centralisée du réveil sur Raspberry Pi.
"""

CONFIG = {
    # Catégorie : Interface I2C
    "i2c": {
        "port": 1,  # Port I2C utilisé (généralement 1 sur Raspberry Pi)
        "retries": 3,  # Nombre de tentatives en cas d'erreur I2C
        "retry_delay": 0.1,  # Délai entre les tentatives I2C (en secondes)
        "rtc_address": 0x68,  # Adresse I2C du module RTC DS3231
        "display_address": 0x3C,  # Adresse I2C de l'écran OLED SH1106
    },
    # Catégorie : Écran OLED
    "display": {
        "font_path": "/usr/share/fonts/opentype/inconsolata/Inconsolata.otf",  # Chemin vers la police de caractères
        "font_sizes": {  # Tailles de police pour différents affichages
            "time": 37,  # Taille pour l'affichage de l'heure
            "menu": 12,  # Taille pour les options des menus
            "settings": 23,  # Taille pour les écrans de réglage
            "freq": 12,  # Ajout : Taille pour les fréquences d'alarmes (petit texte)
            "music_infos": 12,  # Nouvelle : Taille réduite pour infos musique (multiline)
        },
        "i2c_delay": 0.05,  # Delay post-I2C write en secondes (ajuste pour stabilité)
        "blink_interval": 0.5,  # Intervalle de clignotement pour les réglages (en secondes)
        "temp_info_timeout": 15.0,  # Timeout affichage infos musique (secondes)
    },
    # Catégorie : Buzzer
    "buzzer": {
        "pin": 23,  # Broche GPIO pour le buzzer
        "beep_duration": 0.3,  # Durée d'un bip du buzzer (en secondes)
    },
    # Catégorie : Bouton rotatif KY-040
    "rotary": {
        "pins": {  # Broches GPIO pour le KY-040
            "clk": 17,  # Broche pour le signal CLK
            "dt": 22,  # Broche pour le signal DT
            "sw": 27,  # Broche pour le bouton (SW)
        },
        "debounce_ms": 10,  # Délai de débouncing pour les rotations (en millisecondes)
        "switch_debounce_ms": 50,  # Délai de débouncing pour le bouton (en millisecondes)
        "long_press_duration": 1.0,  # Durée minimale pour un appui long (en secondes)
        "repeat_delay": 0.1,  # Intervalle entre appuis répétés pour un appui long (en secondes)
    },
    # Catégorie : Audio
    "audio": {
        "music_dir": "/home/reveil/Musique",  # Dossier contenant les fichiers musicaux
    },
    # Catégorie : Paramètres généraux
    "general": {
        "main_loop_delay": 0.05,  # Délai de la boucle principale du programme (en secondes)
    },
    # Catégorie : Veille et timeouts (defaults, overridés par JSON si présent)
    "settings": {
        "screen_saver_enabled": True,  # Veille active par défaut
        "screen_timeout": 30,  # Temps veille normal (secondes, min 10, max 300)
        "menu_timeout": 30,  # Temps inactivité avant quitter menu (secondes)
        "alarm_screen_on_time": 3600,  # Temps écran allumé pendant alarme (secondes, 1h)
        "alarm_max_duration": 7200,  # Temps max alarme active (secondes, 2h)
        "playback_mode": "sequentiel",  # Mode lecture pour dossiers: "sequentiel" ou "aleatoire"
        "last_sd_path": "/home/reveil/Musique",  # Dernier dossier parcouru pour Carte SD
    },
}
