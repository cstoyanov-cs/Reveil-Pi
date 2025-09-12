import RPi.GPIO as GPIO
import time
import logging

# Configuration du logging pour des outputs clairs
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")


def main():
    # Configuration GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    # Pins des interrupteurs
    ALARM1_PIN = 24
    ALARM2_PIN = 25

    # Setup en entrée avec pull-up interne (HIGH par défaut pour OFF)
    GPIO.setup(ALARM1_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(ALARM2_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    logging.info("Test des interrupteurs lancé. Ctrl+C pour arrêter.")

    try:
        while True:
            # Lecture des états
            alarm1_state = GPIO.input(ALARM1_PIN)
            alarm2_state = GPIO.input(ALARM2_PIN)

            # Log des états
            logging.info(
                f"Alarme 1 (GPIO{ALARM1_PIN}): {'ON (activée)' if alarm1_state == GPIO.LOW else 'OFF (désactivée)'}"
            )
            logging.info(
                f"Alarme 2 (GPIO{ALARM2_PIN}): {'ON (activée)' if alarm2_state == GPIO.LOW else 'OFF (désactivée)'}"
            )

            time.sleep(1)  # Attente 1 seconde avant relecture
    except KeyboardInterrupt:
        logging.info("Test arrêté par l'utilisateur.")
    finally:
        GPIO.cleanup()  # Nettoyage des GPIOs


if __name__ == "__main__":
    main()
