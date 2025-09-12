import RPi.GPIO as GPIO
import subprocess
from src.config.config import CONFIG
from src.components.i2c import I2C
from src.components.rtc import RTC
from src.components.display import Display
from src.components.buzzer import Buzzer
from src.components.rotary import RotaryEncoder
from src.components.time import Time
from src.components.alarms import Alarms
from src.components.audio_manager import AudioManager
from src.components.menu.menu_manager import MenuManager
from src.coordinator.coordinator import Coordinator


def main():
    # Configuration du mode GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    # Initialisation des composants
    i2c = I2C(CONFIG["i2c"])
    rtc = RTC(i2c, CONFIG["i2c"])
    # Créer un config combiné pour Display
    display_config = CONFIG["display"].copy()
    display_config["display_address"] = CONFIG["i2c"]["display_address"]
    display = Display(i2c, display_config)
    buzzer = Buzzer(CONFIG["buzzer"])
    rotary = RotaryEncoder(CONFIG["rotary"])
    audio_manager = AudioManager(CONFIG["audio"]["music_dir"], [])
    time_manager = Time(rtc)
    alarm_manager = Alarms(rtc, buzzer, audio_manager)
    menu_manager = MenuManager(display, time_manager, alarm_manager, audio_manager)
    audio_manager.webradio_stations = menu_manager.webradio_stations
    coordinator = Coordinator(
        time_manager,
        alarm_manager,
        menu_manager,
        rotary,
        display,
        CONFIG,
        audio_manager,
    )

    try:
        coordinator.run()
    except KeyboardInterrupt:
        print("Arrêt du programme par l'utilisateur.")
    except Exception as e:
        print(f"Erreur inattendue : {e}")
    finally:
        # Nettoyage des ressources
        display.clear()
        alarm_manager.stop()
        subprocess.run(
            ["mocp", "-x"], capture_output=True, check=False
        )  # Arrête serveur MOC proprement
        buzzer.cleanup()
        rotary.cleanup()
        i2c.close()
        GPIO.cleanup()


if __name__ == "__main__":
    main()
