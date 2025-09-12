import RPi.GPIO as GPIO
import time
from typing import Optional
from .base_menu import BaseMenu
from src.components.alarms import Alarms


class AlarmActivationSwitchesMenu(BaseMenu):
    """Gère les interrupteurs d'activation/désactivation des alarmes et l'affichage temporaire."""

    def __init__(self, manager, alarm_number: Optional[int] = None):
        super().__init__(manager)
        self.alarm_number = (
            alarm_number  # None si utilisé pour setup/callback uniquement
        )
        self.start_time = time.time() if alarm_number else None
        self.last_render_time = 0  # Pour débounce render
        self.switch_pins = {1: 24, 2: 25}  # GPIO pour interrupteurs (de config.py)
        self.confirmation_mode = False  # Pour afficher "A1 activé" à la fin
        self.annulation_mode = (
            False  # Pour afficher annulation si désactivation pendant temp
        )
        if alarm_number is None:
            self._setup_switches()

    def _setup_switches(self) -> None:
        """Configure les interrupteurs hardware pour override alarmes."""
        for alarm_num, pin in self.switch_pins.items():
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.add_event_detect(
                pin, GPIO.BOTH, callback=self._switch_callback, bouncetime=200
            )
            # Override initial state from switch position
            enabled = GPIO.input(pin) == GPIO.LOW
            state = self.alarm_manager.alarm_states[alarm_num]
            if state["enabled"] != enabled:
                state["enabled"] = enabled
                self.alarm_manager.rtc.set_alarm(
                    alarm_num, state["hour"], state["minute"], enabled
                )

    def _switch_callback(self, channel: int) -> None:
        """Callback pour changement d'interrupteur : override enabled et update RTC/display."""
        self.manager.reset_activity()  # Réveil écran sur action switch
        alarm_num = next(num for num, pin in self.switch_pins.items() if pin == channel)
        enabled = GPIO.input(channel) == GPIO.LOW  # LOW = ON, HIGH = OFF
        state = self.alarm_manager.alarm_states[alarm_num]
        if state["enabled"] != enabled:
            state["enabled"] = enabled
            self.alarm_manager.rtc.set_alarm(
                alarm_num, state["hour"], state["minute"], enabled
            )
            time.sleep(0.1)  # Délai anti-rebond après update
            if not enabled and (
                self.manager.audio_manager.music_playing
                or self.alarm_manager.buzzer.active
            ):
                self.alarm_manager.stop()  # Arrête son si désactivation pendant alarme active
            # Refresh display si en mode normal ou pendant affichage temp
            if self.manager.current_menu is None or (
                isinstance(self.manager.current_menu, AlarmActivationSwitchesMenu)
                and self.manager.current_menu.alarm_number == alarm_num
            ):
                if enabled:
                    self.manager.show_temp_alarm(alarm_num)
                else:
                    if isinstance(
                        self.manager.current_menu, AlarmActivationSwitchesMenu
                    ):
                        # Interrompt et passe à annulation si pendant temp
                        self.manager.current_menu.annulation_mode = True
                        self.manager.current_menu.confirmation_mode = False
                        self.manager.current_menu.start_time = (
                            time.time()
                        )  # Timer 1s pour annulation
                        self.manager.current_menu._render()
                    else:
                        self.manager._render()

    def handle_input(self, events: list[dict], blink_interval: float) -> None:
        """Gère l'affichage temporaire et l'entrée rotary."""
        _ = blink_interval  # Unused but kept for interface; suppress warning
        if self.alarm_number is None:
            return  # Pas d'affichage si utilisé pour setup/callback uniquement
        current_time = time.time()
        assert self.start_time is not None  # Type guard pour Pyright
        if self.annulation_mode:
            # Annulation pendant 1s, puis retour
            if current_time - self.start_time >= 1:
                self.manager.current_menu = None
                self.manager._render()
                return
        elif not self.confirmation_mode:
            # Pendant 5s : heure seulement
            if current_time - self.start_time >= 5:
                self.confirmation_mode = True
                self.start_time = current_time  # Reset timer pour confirmation (2s)
                self._render()
                return
        else:
            # Après 5s : confirmation pendant 2s, puis retour
            if current_time - self.start_time >= 2:
                self.manager.current_menu = None
                self.manager._render()
                return
        # Appui rotary : passer au réglage (seulement pendant heure)
        if not self.confirmation_mode and not self.annulation_mode:
            for event in events:
                if event["button"] == "menu" and event["type"] == "short_press":
                    self.manager._switch_to(
                        "SetAlarmMenu", alarm_number=self.alarm_number, mode="hour"
                    )
                    return
        # Anti-glitch : limite rafraîchissements
        if current_time - self.last_render_time >= 0.5:
            self.last_render_time = current_time
            self._render()

    def _render(self) -> None:
        """Affiche l'heure ou confirmation/annulation."""
        if self.alarm_number is None:
            return
        state = self.alarm_manager.alarm_states[self.alarm_number]
        if self.annulation_mode:
            time_str = f"A{self.alarm_number} désactivé"  # Annulation
            self.display.show_settings(time_str, None, True)
        elif not self.confirmation_mode:
            time_str = f"{state['hour']:02d}:{state['minute']:02d}"  # Seulement heure
            label = f"{'Première' if self.alarm_number == 1 else 'Seconde'} alarme"
            self.display.show_settings(time_str, None, True, label=label)
        else:
            time_str = f"A{self.alarm_number} activé"  # Confirmation sans heure
            self.display.show_settings(time_str, None, True)
