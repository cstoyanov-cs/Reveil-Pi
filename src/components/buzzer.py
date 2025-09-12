import RPi.GPIO as GPIO
import time
import threading

class Buzzer:
    """Gère le buzzer du réveil."""
    def __init__(self, config: dict):
        self.pin = config["pin"]
        self.beep_duration = config["beep_duration"]
        self.active = False
        self.thread = None
        GPIO.setup(self.pin, GPIO.OUT, initial=GPIO.LOW)

    def _buzzer_loop(self) -> None:
        while self.active:
            GPIO.output(self.pin, GPIO.HIGH)
            time.sleep(self.beep_duration)
            GPIO.output(self.pin, GPIO.LOW)
            time.sleep(self.beep_duration)

    def activate(self) -> None:
        if not self.active:
            self.active = True
            self.thread = threading.Thread(target=self._buzzer_loop)
            self.thread.start()

    def stop(self) -> None:
        self.active = False
        if self.thread and self.thread.is_alive():
            self.thread.join()
        GPIO.output(self.pin, GPIO.LOW)

    def cleanup(self) -> None:
        try:
            self.stop()
            GPIO.setup(self.pin, GPIO.IN)
        except:
            pass
