import RPi.GPIO as GPIO
import time
from typing import Optional
from .base_menu import BaseMenu


class AlarmActivationSwitchesMenu(BaseMenu):
    """Gère les interrupteurs GPIO et l'affichage temporaire confirmation."""

    def __init__(self, manager, alarm_number: Optional[int] = None):
        super().__init__(manager)
        self.alarm_number = alarm_number
        self.start_time = time.time() if alarm_number else None
        self.last_render_time = 0
        self.switch_pins = {1: 24, 2: 25}
        self.confirmation_mode = False
        self.annulation_mode = False
        self.desactivation_mode = False  # Nouveau : mode dédié pour désact. globale

        if alarm_number is None:
            self._setup_switches()

    def _setup_switches(self) -> None:
        """Configure les interrupteurs hardware."""
        for alarm_num, pin in self.switch_pins.items():
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.add_event_detect(
                pin, GPIO.BOTH, callback=self._switch_callback, bouncetime=200
            )

            # Override initial state
            enabled = GPIO.input(pin) == GPIO.LOW
            state = self.alarm_manager.alarm_states[alarm_num]
            if state["enabled"] != enabled:
                state["enabled"] = enabled
                self.alarm_manager.rtc.set_alarm(
                    alarm_num, state["hour"], state["minute"], enabled
                )

    def _switch_callback(self, channel: int) -> None:
        """
        Callback switch PRIORITAIRE : force fermeture menu + affichage.

        Correction critique : si un menu est ouvert, le switch le ferme
        immédiatement pour afficher la confirmation alarme.
        """
        self.manager.reset_activity()

        # Identifier alarme
        alarm_num = next(num for num, pin in self.switch_pins.items() if pin == channel)
        enabled = GPIO.input(channel) == GPIO.LOW
        state = self.alarm_manager.alarm_states[alarm_num]

        if state["enabled"] == enabled:
            return  # Pas de changement

        # Update état + RTC
        state["enabled"] = enabled
        self.alarm_manager.rtc.set_alarm(
            alarm_num, state["hour"], state["minute"], enabled
        )
        time.sleep(0.1)

        # Arrêt musique si désactivation pendant alarme
        if not enabled and (
            self.manager.audio_manager.music_playing or self.alarm_manager.buzzer.active
        ):
            self.alarm_manager.stop()

        #  PRIORITÉ SWITCH : Force fermeture menu
        if enabled:
            # Activation : ferme tout menu + affiche confirmation
            print(f"[SWITCH] A{alarm_num} activée - PRIORITÉ switch")
            self.manager.current_menu = None
            self.manager.show_temp_alarm(alarm_num)
        else:
            # Désactivation : création manuelle pour set mode avant render (alternative sans param)
            print(f"[SWITCH] A{alarm_num} désact")
            temp_menu = AlarmActivationSwitchesMenu(
                self.manager, alarm_number=alarm_num
            )
            temp_menu.desactivation_mode = True
            temp_menu.start_time = time.time()
            self.manager.current_menu = temp_menu
            temp_menu._render()  # Force affichage direct

    def handle_input(self, events: list[dict], blink_interval: float) -> None:
        _ = blink_interval  # Paramètre requis par BaseMenu mais non utilisé
        """Gère l'affichage temporaire : heure 5s → confirmation 2s → retour."""
        if self.alarm_number is None:
            return

        current_time = time.time()
        assert self.start_time is not None

        # Mode annulation : 1s puis retour
        if self.annulation_mode:
            if current_time - self.start_time >= 1:
                self.manager.current_menu = None
                self.manager._render()
                return

        # Mode désactivation : 2s puis retour
        elif self.desactivation_mode:
            if current_time - self.start_time >= 2:
                self.manager.current_menu = None
                self.manager._render()
                return

        # Mode heure : 5s
        elif not self.confirmation_mode:
            if current_time - self.start_time >= 5:
                self.confirmation_mode = True
                self.start_time = current_time
                self._render()
                return

            # Appui rotary pendant heure : passage config
            for event in events:
                if event["button"] == "menu" and event["type"] == "short_press":
                    self.manager._switch_to(
                        "SetAlarmMenu", alarm_number=self.alarm_number, mode="hour"
                    )
                    return

        # Mode confirmation : 2s puis retour
        else:
            if current_time - self.start_time >= 2:
                self.manager.current_menu = None
                self.manager._render()
                return

        # Throttle render (500ms min)
        if current_time - self.last_render_time >= 0.5:
            self.last_render_time = current_time
            self._render()

    def _render(self) -> None:
        """Affiche heure / confirmation / annulation."""
        if self.alarm_number is None:
            return

        state = self.alarm_manager.alarm_states[self.alarm_number]

        if self.desactivation_mode:
            time_str = f"A{self.alarm_number} désact"
            self.display.show_settings(time_str, None, True)
            return

        if self.annulation_mode:
            time_str = f"A{self.alarm_number} désact"
            self.display.show_settings(time_str, None, True)

        elif not self.confirmation_mode:
            # Heure seulement
            time_str = f"{state['hour']:02d}:{state['minute']:02d}"
            label = f"{'Première' if self.alarm_number == 1 else 'Seconde'} alarme"
            self.display.show_settings(time_str, None, True, label=label)

        else:
            # Confirmation
            time_str = f"A{self.alarm_number} activée"
            self.display.show_settings(time_str, None, True)
