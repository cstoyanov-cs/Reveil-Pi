import RPi.GPIO as GPIO
import time

print("DÉBUT: Initialisation du script (lgpio)")

# Vérifier l'importation
try:
    print("DEBUG: Importation de RPi.GPIO réussie")
except Exception as e:
    print(f"ERREUR: Échec de l'importation: {e}")
    exit(1)

# Définir le mode BCM
try:
    GPIO.setmode(GPIO.BCM)
    print("DEBUG: Mode BCM défini")
    time.sleep(0.1)  # Délai pour initialisation
except Exception as e:
    print(f"ERREUR: Échec de setmode: {e}")
    exit(1)

# Vérifier le mode
mode = GPIO.getmode()
if mode == GPIO.BCM:
    print("DEBUG: Mode confirmé comme BCM")
elif mode == GPIO.BOARD:
    print("DEBUG: Mode confirmé comme BOARD")
else:
    print("DEBUG: Mode non défini (None)")
    exit(1)

# Broches du KY-040
clk = 17
dt = 22
sw = 27
print(f"DEBUG: Broches définies (CLK={clk}, DT={dt}, SW={sw})")

# Configurer les broches
try:
    GPIO.setup(clk, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    print("DEBUG: Broche CLK configurée")
    GPIO.setup(dt, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    print("DEBUG: Broche DT configurée")
    GPIO.setup(sw, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    print("DEBUG: Broche SW configurée")
except Exception as e:
    print(f"ERREUR: Échec de la configuration: {e}")
    GPIO.cleanup()
    exit(1)

last_clk = GPIO.input(clk)
print("DEBUG: État initial de CLK lu")

def rotary_callback(channel):
    global last_clk
    clk_state = GPIO.input(clk)
    dt_state = GPIO.input(dt)
    if clk_state != last_clk:
        time.sleep(0.01)  # Débouncing
        dt_state = GPIO.input(dt)
        if dt_state != clk_state:
            print("DEBUG: Rotation horaire (Up)")
        else:
            print("DEBUG: Rotation anti-horaire (Down)")
    last_clk = clk_state

def switch_callback(channel):
    if GPIO.input(sw) == GPIO.LOW:
        print("DEBUG: Clic (Menu)")
        time.sleep(0.2)  # Anti-rebond

# Configurer les interruptions
try:
    GPIO.add_event_detect(clk, GPIO.BOTH, callback=rotary_callback, bouncetime=15)
    print("DEBUG: Interruption CLK configurée")
    GPIO.add_event_detect(sw, GPIO.FALLING, callback=switch_callback, bouncetime=200)
    print("DEBUG: Interruption SW configurée")
except RuntimeError as e:
    print(f"ERREUR: Échec des interruptions: {e}")
    GPIO.cleanup()
    exit(1)

try:
    print("En attente d'événements KY-040...")
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("DEBUG: Programme interrompu")
finally:
    GPIO.cleanup()
    print("DEBUG: GPIO nettoyées")
