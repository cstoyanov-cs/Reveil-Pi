import RPi.GPIO as GPIO
import time

# Configuration GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# Pin du buzzer (GPIO 23)
BUZZER_PIN = 23

# Setup du pin comme sortie
try:
    GPIO.setup(BUZZER_PIN, GPIO.OUT)
    print("DEBUG: Pin buzzer configuré (GPIO 23)")
except Exception as e:
    print(f"ERREUR: Échec configuration GPIO : {e}")
    GPIO.cleanup()
    exit(1)

def test_buzzer():
    """Teste le buzzer avec 5 bips (500ms ON, 500ms OFF)."""
    print("DÉBUT: Test du buzzer (5 bips)")
    try:
        for _ in range(5):
            GPIO.output(BUZZER_PIN, GPIO.HIGH)  # Active buzzer
            print("Buzzer ON")
            time.sleep(0.5)  # 500ms ON
            GPIO.output(BUZZER_PIN, GPIO.LOW)   # Désactive buzzer
            print("Buzzer OFF")
            time.sleep(0.5)  # 500ms OFF
        print("FIN: Test terminé")
    except Exception as e:
        print(f"ERREUR: Échec test buzzer : {e}")
    finally:
        GPIO.cleanup()
        print("DEBUG: GPIO nettoyées")

if __name__ == "__main__":
    try:
        test_buzzer()
    except KeyboardInterrupt:
        print("DEBUG: Test interrompu")
        GPIO.cleanup()