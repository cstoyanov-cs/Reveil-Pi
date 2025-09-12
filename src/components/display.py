from luma.core.interface.serial import i2c as luma_i2c
from luma.core.render import canvas
from luma.oled.device import sh1106
from PIL import ImageFont
from src.components.i2c import I2C
import time


class Display:
    """Gère l'affichage sur l'OLED SH1106."""

    def __init__(self, i2c: I2C, config: dict):
        self.i2c = i2c
        self.address = config[
            "display_address"
        ]  # Fixed: "address" -> "display_address"
        self.serial = None
        self.device = None
        self.font_path = config["font_path"]
        self.fonts = {
            "time": ImageFont.truetype(
                config["font_path"], config["font_sizes"]["time"]
            ),
            "menu": ImageFont.truetype(
                config["font_path"], config["font_sizes"]["menu"]
            ),
            "settings": ImageFont.truetype(
                config["font_path"], config["font_sizes"]["settings"]
            ),
            "freq": ImageFont.truetype(
                config["font_path"], config["font_sizes"]["freq"]
            ),
        }
        self.i2c_delay = config.get("i2c_delay", 0.02)  # Défaut 20ms si absent
        self.last_update = 0
        self.update_interval = 0.05
        self.blink_interval = config["blink_interval"]
        self.is_on = True  # État initial allumé
        self._init_oled()

    def _init_oled(self) -> None:
        """Initialise ou réinitialise l'OLED."""
        try:
            if self.serial:
                self.serial.cleanup()
        except (AttributeError, OSError):
            pass
        try:
            self.serial = luma_i2c(port=self.i2c.port, address=self.address)
            self.device = sh1106(self.serial)
            self.device.show()  # Allumé par défaut
        except OSError as e:
            print(f"Erreur initialisation OLED : {e}")
            self.device = None

    def _post_write_sleep(self) -> None:
        """Applique delay configurable après write I2C pour stabilité bus."""
        time.sleep(self.i2c_delay)  # Centralisé, évite timeouts surcharge

    def power_on(self) -> None:
        """Allume l'écran."""
        if self.device and not self.is_on:
            self.device.show()
            self.is_on = True

    def power_off(self) -> None:
        """Éteint l'écran."""
        if self.device and self.is_on:
            self.device.hide()
            self.is_on = False

    def _can_update(self) -> bool:
        """Vérifie si un rafraîchissement est autorisé (débouncing)."""
        current_time = time.time()
        if current_time - self.last_update >= self.update_interval:
            self.last_update = current_time
            return True
        return False

    def show_time(
        self,
        time_str: str,
        alarm_indicators: tuple[bool, bool],
        alarm_frequencies: tuple[str, str],
        playing: bool = False,  # Ajout pour icône play
    ) -> None:
        """Affiche l'heure avec les indicateurs d'alarme et fréquences."""
        if not self._can_update():
            return
        if not self.device:
            self._init_oled()
            if not self.device:
                return
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                with canvas(self.device) as draw:
                    draw.text((20, 20), time_str, font=self.fonts["time"], fill="white")
                    if alarm_indicators[0]:
                        draw.rectangle(
                            (108, 24, 110, 27), fill="white"
                        )  # Plus petit 3x3
                        draw.text(
                            (116, 15),
                            alarm_frequencies[0],
                            font=self.fonts["freq"],
                            fill="white",
                        )
                    if alarm_indicators[1]:
                        draw.rectangle(
                            (108, 37, 110, 40), fill="white"
                        )  # Vertical haut
                        draw.rectangle((108, 45, 110, 48), fill="white")  # Vertical bas
                        draw.text(
                            (116, 33),
                            alarm_frequencies[1],
                            font=self.fonts["freq"],
                            fill="white",
                        )
                    if playing:
                        # Icône play (triangle) en bas droit
                        draw.polygon([(110, 50), (110, 60), (120, 55)], fill="white")
                # Après with canvas(self.device) as draw: bloc
                self._post_write_sleep()
                break
            except OSError as e:
                if attempt < max_attempts - 1:
                    print(
                        f"Erreur affichage OLED (show_time, tentative {attempt + 1}) : {e}"
                    )
                    self._init_oled()
                    self._post_write_sleep()
                else:
                    print(
                        f"Échec affichage OLED (show_time) après {max_attempts} tentatives : {e}"
                    )
                    self.device = None

    def show_menu(self, options: list[str], selected_index: int) -> None:
        """Affiche un menu avec défilement basé sur l'option sélectionnée."""
        if not self._can_update():
            return
        if not self.device:
            self._init_oled()
            if not self.device:
                return
        line_height = 14
        max_visible_lines = 4
        start_index = max(
            0,
            min(
                selected_index - max_visible_lines // 2,
                len(options) - max_visible_lines,
            ),
        )
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                with canvas(self.device) as draw:
                    for i in range(
                        start_index, min(start_index + max_visible_lines, len(options))
                    ):
                        option = options[i]
                        y = 5 + (i - start_index) * line_height
                        selected = i == selected_index
                        if selected:
                            text_width = draw.textlength(
                                option, font=self.fonts["menu"]
                            )
                            draw.rectangle(
                                (
                                    10,
                                    y - 2,
                                    10 + text_width,
                                    y + self.fonts["menu"].size,
                                ),
                                fill="white",
                            )
                            draw.text(
                                (10, y), option, font=self.fonts["menu"], fill="black"
                            )
                        else:
                            draw.text(
                                (10, y), option, font=self.fonts["menu"], fill="white"
                            )
                self._post_write_sleep()
                break
            except OSError as e:
                if attempt < max_attempts - 1:
                    print(
                        f"Erreur affichage OLED (show_menu, tentative {attempt + 1}) : {e}"
                    )
                    self._init_oled()
                    self._post_write_sleep()
                else:
                    print(
                        f"Échec affichage OLED (show_menu) après {max_attempts} tentatives : {e}"
                    )
                    self.device = None

    def show_settings(
        self, time_str: str, blink_field: str, blink_state: bool, label: str = None
    ) -> None:
        """Affiche un réglage avec clignotement du champ modifié et label optionnel."""
        if not self._can_update():
            return
        if not self.device:
            self._init_oled()
            if not self.device:
                return
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                with canvas(self.device) as draw:
                    font_time = self.fonts["time"]  # 30px pour heure
                    font_label = self.fonts["menu"]  # 12px pour label
                    font_settings = self.fonts["settings"]  # 20px pour autres
                    font_menu = self.fonts["menu"]  # 12px pour multiligne musique

                    # Label au-dessus si fourni
                    if label:
                        label_width = draw.textlength(label, font=font_label)
                        label_x = (self.device.width - label_width) // 2  # Centrage
                        draw.text((label_x, 5), label, font=font_label, fill="white")

                    y = 25 if label else 20  # Décalage si label

                    # Gestion multiligne si \n dans text_str (ex. pour musique)
                    lines = time_str.split("\n")
                    if len(lines) > 1:
                        # Multiligne : font petite, centrage par ligne, pas de blink
                        y = 0
                        for i, line in enumerate(lines):
                            text_width = draw.textlength(line, font=font_menu)
                            x = (self.device.width - text_width) // 2  # Centrage
                            draw.text((x, y), line, font=font_menu, fill="white")
                            y += 12  # Espacement pour font 12px
                    else:
                        # Cas mono-ligne : logique existante avec blink
                        # Choisir font : grande pour clignotement heure/minute, settings sinon
                        if blink_field in ["hours", "minutes"] and ":" in time_str:
                            font = font_time  # 30px pour clignotement heure/minute
                        else:
                            font = font_settings  # 20px pour autres réglages
                        text_width = draw.textlength(time_str, font=font)
                        x = (self.device.width - text_width) // 2  # Centrage
                        if blink_field == "hours" and ":" in time_str:
                            hours, minutes = time_str.split(":")
                            if not blink_state:
                                partial_width = draw.textlength(hours + ":", font=font)
                                draw.text(
                                    (x + partial_width, y),
                                    minutes,
                                    font=font,
                                    fill="white",
                                )
                            else:
                                draw.text((x, y), time_str, font=font, fill="white")
                        elif blink_field == "minutes" and ":" in time_str:
                            hours, minutes = time_str.split(":")
                            if not blink_state:
                                draw.text((x, y), hours + ":", font=font, fill="white")
                            else:
                                draw.text((x, y), time_str, font=font, fill="white")
                        else:
                            draw.text((x, y), time_str, font=font, fill="white")
                time.sleep(0.015)
                break
            except OSError as e:
                if attempt < max_attempts - 1:
                    print(
                        f"Erreur affichage OLED (show_settings, tentative {attempt + 1}) : {e}"
                    )
                    self._init_oled()
                    self._post_write_sleep()

                else:
                    print(
                        f"Échec affichage OLED (show_settings) après {max_attempts} tentatives : {e}"
                    )
                    self.device = None

    def show_date_view(
        self, day_str: str, date_str: str, options: list[str], selected_index: int
    ) -> None:
        """Affiche jour en haut, date en dessous, options horizontales en bas."""
        if not self._can_update() or not self.is_on:
            return
        if not self.device:
            self._init_oled()
            if not self.device:
                return
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                with canvas(self.device) as draw:
                    font_date = self.fonts["settings"]
                    # Jour en haut, centrée, 20px
                    day_width = draw.textlength(day_str, font=font_date)
                    day_x = (self.device.width - day_width) // 2
                    draw.text((day_x, 5), day_str, font=font_date, fill="white")
                    # Date en dessous, centrée, 20px
                    date_width = draw.textlength(date_str, font=font_date)
                    date_x = (self.device.width - date_width) // 2
                    draw.text((date_x, 25), date_str, font=font_date, fill="white")
                    # Options horizontales en bas, 12px, highlight
                    font_opt = self.fonts["menu"]
                    x_positions = [10, 70]  # Ajuste si texte trop long
                    for i, option in enumerate(options):
                        y = 45
                        x = x_positions[i]
                        selected = i == selected_index
                        if selected:
                            text_width = draw.textlength(option, font=font_opt)
                            draw.rectangle(
                                (x, y - 2, x + text_width, y + font_opt.size),
                                fill="white",
                            )
                            draw.text((x, y), option, font=font_opt, fill="black")
                        else:
                            draw.text((x, y), option, font=font_opt, fill="white")

                self._post_write_sleep()
                break
            except OSError as e:
                if attempt < max_attempts - 1:
                    print(
                        f"Erreur affichage OLED (show_date_view, tentative {attempt + 1}) : {e}"
                    )
                    self._init_oled()
                    self._post_write_sleep()
                else:
                    print(
                        f"Échec affichage OLED (show_date_view) après {max_attempts} tentatives : {e}"
                    )
                    self.device = None

    def clear(self) -> None:
        """Efface l'écran."""
        if not self.device:
            self._init_oled()
            if not self.device:
                return
        try:
            with canvas(self.device) as draw:
                draw.rectangle((0, 0, self.device.width, self.device.height), fill=0)
            self._post_write_sleep()
        except OSError as e:
            print(f"Erreur effacement OLED : {e}")
            self._init_oled()

    def _reset_oled(self) -> None:
        """Réinitialise l'OLED (compatibilité avec versions précédentes)."""
        self._init_oled()
