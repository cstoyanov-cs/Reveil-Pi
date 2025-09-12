import RPi.GPIO as GPIO
import time


class RotaryEncoder:
    """Gère l'encodeur rotatif KY-040."""

    def __init__(self, config: dict):
        """Initialise le KY-040 avec la configuration fournie."""
        self.pins = config["pins"]
        self.debounce_ms = config["debounce_ms"]
        self.switch_debounce_ms = config["switch_debounce_ms"]
        self.long_press_duration = config["long_press_duration"]
        self.repeat_delay = config["repeat_delay"]
        self.events = []
        self.last_status = None
        self.last_switch_status = None
        self.last_switch_time = 0
        self.switch_press_time = 0
        self.switch_pressed = False
        self.long_detected = False
        self._init_gpio()

    def _init_gpio(self) -> None:
        """Initialise les broches GPIO avec RPi.GPIO."""
        GPIO.setup(self.pins["clk"], GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.pins["dt"], GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.pins["sw"], GPIO.IN, pull_up_down=GPIO.PUD_UP)
        self.last_status = (GPIO.input(self.pins["dt"]) << 1) | GPIO.input(
            self.pins["clk"]
        )
        self.last_switch_status = GPIO.input(self.pins["sw"])
        GPIO.add_event_detect(
            self.pins["clk"],
            GPIO.BOTH,
            callback=self._rotary_callback,
            bouncetime=self.debounce_ms,
        )
        GPIO.add_event_detect(
            self.pins["dt"],
            GPIO.BOTH,
            callback=self._rotary_callback,
            bouncetime=self.debounce_ms,
        )
        GPIO.add_event_detect(
            self.pins["sw"],
            GPIO.BOTH,
            callback=self._switch_callback,
            bouncetime=self.switch_debounce_ms,
        )

    def _rotary_callback(self, channel):
        """Gère les changements sur CLK ou DT."""
        new_status = (GPIO.input(self.pins["dt"]) << 1) | GPIO.input(self.pins["clk"])
        if new_status == self.last_status:
            return
        transition = (self.last_status << 2) | new_status
        if transition == 0b1110:
            self.events.append({"button": "up", "type": "short_press"})
        elif transition == 0b1101:
            self.events.append({"button": "down", "type": "short_press"})
        self.last_status = new_status

    def _switch_callback(self, channel):
        """Gère les changements sur SW."""
        current_time = time.time()
        new_status = GPIO.input(self.pins["sw"])
        if new_status == self.last_switch_status:
            return
        self.last_switch_status = new_status
        if new_status == GPIO.LOW:  # Appui
            self.switch_pressed = True
            self.switch_press_time = current_time
            self.last_switch_time = current_time
            self.long_detected = False  # Reset flag sur nouvel appui
        else:  # Relâchement
            if (
                not self.long_detected
                and current_time - self.switch_press_time < self.long_press_duration
            ):
                self.events.append({"button": "menu", "type": "short_press"})
            self.switch_pressed = False
            self.long_detected = False  # Reset

    def get_events(self) -> list[dict]:
        """Retourne les événements détectés (up, down, menu)."""
        events = self.events.copy()
        self.events.clear()
        current_time = time.time()
        if (
            self.switch_pressed
            and not self.long_detected
            and current_time - self.switch_press_time >= self.long_press_duration
        ):
            events.append({"button": "menu", "type": "long_press"})
            self.long_detected = True  # Flag pour éviter multiple et short après
        return events

    def cleanup(self) -> None:
        """Nettoie les ressources GPIO."""
        try:
            GPIO.remove_event_detect(self.pins["clk"])
            GPIO.remove_event_detect(self.pins["dt"])
            GPIO.remove_event_detect(self.pins["sw"])
        except:
            pass
