import RPi.GPIO as GPIO
import time
import os
import logging
from typing import Optional
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


def main() -> None:
    # Configuration logging dès le début
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logger = logging.getLogger(__name__)

    logger.info("Démarrage réveil Raspberry Pi...")

    # Configuration du mode GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    # Configuration socket MPD
    os.environ["MPD_HOST"] = "/run/mpd/socket"

    # Déclaration explicite des variables avec type Optional
    i2c: Optional[I2C] = None
    display: Optional[Display] = None
    buzzer: Optional[Buzzer] = None
    rotary: Optional[RotaryEncoder] = None
    audio_manager: Optional[AudioManager] = None
    alarm_manager: Optional[Alarms] = None

    # Initialisation des composants
    try:
        logger.info("Initialisation composants hardware...")

        i2c = I2C(CONFIG["i2c"])
        rtc = RTC(i2c, CONFIG["i2c"])

        # Configuration display combinée
        display_config = CONFIG["display"].copy()
        display_config["display_address"] = CONFIG["i2c"]["display_address"]
        display = Display(i2c, display_config)

        buzzer = Buzzer(CONFIG["buzzer"])
        rotary = RotaryEncoder(CONFIG["rotary"])

        # Composants logiciels
        audio_manager = AudioManager(CONFIG["audio"]["music_dir"], [])
        time_manager = Time(rtc)
        alarm_manager = Alarms(rtc, buzzer, audio_manager)
        menu_manager = MenuManager(display, time_manager, alarm_manager, audio_manager)

        # Liaisons croisées
        display.manager = menu_manager
        audio_manager.webradio_stations = menu_manager.webradio_stations

        # Coordinateur principal
        coordinator = Coordinator(
            time_manager,
            alarm_manager,
            menu_manager,
            rotary,
            display,
            CONFIG,
            audio_manager,
        )

        logger.info("Initialisation terminée - Lancement boucle principale")

        # Boucle principale
        coordinator.run()

    except KeyboardInterrupt:
        logger.info("Arrêt demandé par utilisateur (Ctrl+C)")

    except Exception as e:
        logger.error(f"Erreur fatale: {e}", exc_info=True)

    finally:
        # Cleanup avec timeout global
        logger.info("Nettoyage des ressources...")
        cleanup_start = time.time()

        try:
            # Audio en premier (critique si MPD actif)
            if audio_manager is not None:
                audio_manager.cleanup()

            # Composants hardware (ordre non critique)
            if display is not None:
                display.clear()

            if alarm_manager is not None:
                alarm_manager.stop()

            if buzzer is not None:
                buzzer.cleanup()

            if rotary is not None:
                rotary.cleanup()

        except Exception as e:
            logger.warning(f"Erreur pendant cleanup: {e}")

        # Cleanup I2C/GPIO toujours exécuté
        try:
            if i2c is not None:
                i2c.close()
        except Exception:
            pass

        try:
            GPIO.cleanup()
        except Exception:
            pass

        elapsed = time.time() - cleanup_start
        logger.info(f"Nettoyage terminé ({elapsed:.2f}s)")
        logger.info("Réveil arrêté proprement")


if __name__ == "__main__":
    main()
