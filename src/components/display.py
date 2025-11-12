from typing import Optional, TYPE_CHECKING
from luma.core.interface.serial import i2c as luma_i2c
from luma.core.render import canvas
from luma.oled.device import sh1106
from PIL import ImageFont
from src.components.i2c import I2C
import time

if TYPE_CHECKING:
    from src.components.menu.menu_manager import MenuManager


class Display:
    """Gère l'affichage sur l'OLED SH1106."""

    def __init__(self, i2c: I2C, config: dict):
        self.i2c = i2c
        self.address = config["display_address"]  # Adresse I2C de l'écran
        self.serial = None
        self.device = None
        self.font_path = config["font_path"]
        self.font_sizes = config["font_sizes"]
        self._fonts_cache = {}
        self.i2c_delay = config.get(
            "i2c_delay", 0.02
        )  # Délai par défaut pour la stabilité I2C
        self.last_update = 0  # Dernier timestamp de mise à jour
        self.update_interval = (
            0.3  # Intervalle minimum entre les mises à jour (secondes)
        )
        self.blink_interval = config["blink_interval"]  # Intervalle de clignotement
        self.is_on = True  # État initial de l'écran (allumé)
        self.manager: Optional["MenuManager"] = (
            None  # Référence au gestionnaire de menu
        )
        self._init_oled()  # Initialise l'écran OLED

    def _init_oled(self) -> None:
        """Initialise ou réinitialise l'OLED."""
        try:
            if self.serial:
                self.serial.cleanup()  # Nettoie l'interface série si elle existe
        except (AttributeError, OSError):
            pass  # Ignore les erreurs si l'interface n'est pas initialisée
        try:
            self.serial = luma_i2c(port=self.i2c.port, address=self.address)
            self.device = sh1106(self.serial)
            self.device.show()  # Allume l'écran par défaut
        except OSError:
            self.device = None  # Marque l'écran comme non disponible

    @property
    def fonts(self) -> dict:
        """Charge fonts à la demande (lazy)."""
        for name, size in self.font_sizes.items():
            if name not in self._fonts_cache:
                self._fonts_cache[name] = ImageFont.truetype(self.font_path, size)
        return self._fonts_cache

    def _post_write_sleep(self) -> None:
        """Applique un délai configurable après une écriture I2C pour stabiliser le bus."""
        time.sleep(self.i2c_delay)

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
        """Vérifie si rafraîchissement autorisé."""
        current_time = time.time()
        # Réduit à 0.05s pour permettre clignotement fluide
        if current_time - self.last_update < 0.02:
            return False
        self.last_update = current_time
        return True

    def show_menu(self, options: list[str], selected_index: int) -> None:
        """Affiche un menu avec défilement basé sur l'option sélectionnée."""
        if not self._can_update():
            return  # Ne rafraîchit pas si trop fréquent
        if not self.device:
            self._init_oled()  # Réinitialise l'écran si nécessaire
            if not self.device:
                return  # Quitte si l'écran n'est pas disponible
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
                    if self.device:
                        draw.rectangle(
                            (0, 0, self.device.width, self.device.height), fill=0
                        )  # Efface l'écran avant d'afficher le menu
                    for i in range(
                        start_index, min(start_index + max_visible_lines, len(options))
                    ):
                        option = options[i]
                        y = 5 + (i - start_index) * line_height
                        selected = i == selected_index
                        if selected:
                            # Met en surbrillance l'option sélectionnée
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
                self._post_write_sleep()  # Applique un délai après l'écriture
                break
            except OSError:
                if attempt < max_attempts - 1:
                    self._init_oled()  # Réinitialise l'écran en cas d'erreur
                    self._post_write_sleep()
                else:
                    self.device = None  # Marque l'écran comme non disponible

    def show_time(
        self,
        time_str: str,
        alarm_indicators: tuple[bool, bool],
        alarm_frequencies: tuple[str, str],
        playing: bool = False,
        music_source: Optional[str] = None,
        mpd_unavailable: bool = False,
    ) -> None:
        """Affiche l'heure avec les indicateurs d'alarme et fréquences, plus indicateur mode lecture."""
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
                    # Affiche l'heure au centre
                    time_width = draw.textbbox(
                        (0, 0), time_str, font=self.fonts["time"]
                    )[2]
                    x = (128 - time_width) // 2
                    draw.text((x, 20), time_str, font=self.fonts["time"], fill="white")
                    # AJOUT : Icône erreur MPD (croix en haut à droite)
                    if mpd_unavailable:
                        draw.text((118, 5), "B", font=self.fonts["freq"], fill="white")
                    # Affiche les indicateurs d'alarme
                    if alarm_indicators[0]:
                        draw.rectangle((115, 24, 117, 27), fill="white")
                        draw.text(
                            (123, 15),
                            alarm_frequencies[0],
                            font=self.fonts["freq"],
                            fill="white",
                        )
                    if alarm_indicators[1]:
                        draw.rectangle((115, 37, 117, 40), fill="white")
                        draw.rectangle((115, 45, 117, 48), fill="white")
                        draw.text(
                            (123, 33),
                            alarm_frequencies[1],
                            font=self.fonts["freq"],
                            fill="white",
                        )
                    # Affiche l'icône de lecture si la musique est en cours
                    if playing:
                        draw.polygon([(110, 50), (110, 60), (120, 55)], fill="white")
                    # Affiche l'indicateur de mode lecture (Carte SD ou Webradio)
                    if music_source == "sd" and self.manager is not None:
                        mode = self.manager.settings.get("playback_mode", "sequentiel")
                        if mode == "aleatoire":
                            draw.rectangle(
                                (100, 55, 103, 58), fill="white"
                            )  # Icône shuffle
                            draw.rectangle((103, 52, 106, 55), fill="white")
                        else:
                            draw.rectangle(
                                (100, 55, 106, 58), fill="white"
                            )  # Icône lecture séquentielle
                    elif music_source == "webradio":
                        draw.ellipse((100, 52, 103, 55), fill="white")  # Icône Webradio
                        draw.ellipse((98, 50, 105, 57), fill="white")
                self._post_write_sleep()
                break
            except OSError:
                if attempt < max_attempts - 1:
                    self._init_oled()
                    self._post_write_sleep()
                else:
                    self.device = None

    def show_music_player(
        self,
        artist: str,
        title: str,
        elapsed: str,
        total: str,
        progress: float,
        is_playing: bool,
        source: str = "sd",
    ) -> None:
        """
        Affiche un lecteur de musique style Rockbox avec barre de progression.

        Args:
            artist: Nom de l'artiste
            title: Titre du morceau
            elapsed: Temps écoulé (format "mm:ss")
            total: Durée totale (format "mm:ss")
            progress: Progression (0.0 à 1.0)
            is_playing: True si en lecture, False si en pause
            source: "sd" ou "webradio"
        """
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
                    font_small = self.fonts["music_infos"]  # Taille 12

                    # Ligne 1 : Artiste (tronqué si nécessaire)
                    artist_display = (
                        artist if len(artist) <= 21 else artist[:18] + "..."
                    )
                    draw.text((2, 0), artist_display, font=font_small, fill="white")

                    # Ligne 2 : Titre (tronqué si nécessaire)
                    title_display = title if len(title) <= 21 else title[:18] + "..."
                    draw.text((2, 12), title_display, font=font_small, fill="white")

                    if source == "sd":
                        # Ligne 3 : Barre de progression
                        bar_y = 26
                        bar_width = 124  # Largeur totale - marges
                        bar_height = 6

                        # Cadre de la barre
                        draw.rectangle(
                            (2, bar_y, 2 + bar_width, bar_y + bar_height),
                            outline="white",
                            fill=0,
                        )

                        # Remplissage de la barre
                        if progress > 0:
                            fill_width = int((bar_width - 2) * progress)
                            if fill_width > 0:
                                draw.rectangle(
                                    (
                                        3,
                                        bar_y + 1,
                                        3 + fill_width,
                                        bar_y + bar_height - 1,
                                    ),
                                    fill="white",
                                )

                        # Ligne 4 : Temps (gauche) et icône play/pause (droite)
                        time_str = f"{elapsed} / {total}"
                        draw.text((2, 35), time_str, font=font_small, fill="white")

                        # Icône play/pause en bas à droite
                        if is_playing:
                            # Triangle play
                            draw.polygon(
                                [(110, 36), (110, 46), (120, 41)], fill="white"
                            )
                        else:
                            # Barres pause
                            draw.rectangle((110, 36, 113, 46), fill="white")
                            draw.rectangle((117, 36, 120, 46), fill="white")

                    else:  # webradio
                        # Ligne 3 : "Streaming..."
                        draw.text(
                            (2, 26), "Streaming...", font=font_small, fill="white"
                        )

                        # Ligne 4 : Temps et icône
                        draw.text((2, 38), elapsed, font=font_small, fill="white")

                        # Icône webradio (ondes)
                        draw.ellipse((108, 38, 112, 42), outline="white")
                        draw.ellipse((105, 35, 115, 45), outline="white")
                        draw.ellipse((102, 32, 118, 48), outline="white")

                self._post_write_sleep()
                break
            except OSError:
                if attempt < max_attempts - 1:
                    self._init_oled()
                    self._post_write_sleep()
                else:
                    self.device = None

    def show_settings(
        self,
        time_str: str,
        blink_field: Optional[str] = None,
        blink_state: bool = True,
        label: Optional[str] = None,
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
                    font_time = self.fonts["time"]
                    font_label = self.fonts["menu"]
                    font_settings = self.fonts["settings"]
                    # Affiche le label si fourni
                    if label:
                        label_width = draw.textlength(label, font=font_label)
                        label_x = (128 - label_width) // 2
                        draw.text((label_x, 5), label, font=font_label, fill="white")
                    y = 25 if label else 20
                    # Détection spéciale pour infos musique (prefix "Titre:" → police petite)
                    is_music_info = "Titre:" in time_str
                    lines = time_str.split("\n")
                    if is_music_info or len(lines) > 1:
                        # Utilise police "music_infos" pour musique/multiline (ex: infos musique)
                        font = self.fonts["music_infos"]
                        y = 0  # Reset Y pour affichage en haut (compact)
                        # Si musique sans \n, split manuel sur " - " pour titre/artiste
                        if is_music_info and len(lines) == 1 and " - " in time_str:
                            try:
                                parts = time_str.split(" - ", 1)
                                if len(parts) == 2 and parts[1].strip():
                                    lines = parts
                            except Exception:
                                pass  # Garde lines original si erreur
                        for line in lines:
                            if line.strip():  # Ignore lignes vides
                                text_width = draw.textlength(line, font=font)
                                x = (128 - text_width) // 2
                                draw.text((x, y), line, font=font, fill="white")
                                # Hauteur dynamique basée sur la font (env. 10px pour taille 10)
                                y += (
                                    font.getbbox("A")[3] - font.getbbox("A")[1] + 2
                                )  # +2 pour espacement
                    else:
                        # Détection simple d'heure (HH:MM) pour police grosse
                        if (
                            len(time_str) == 5
                            and time_str[2] == ":"
                            and time_str[:2].isdigit()
                            and time_str[3:].isdigit()
                        ):
                            font = font_time  # Police grosse seulement pour "HH:MM"
                        else:
                            font = font_settings  # Petite pour les autres textes

                        text_width = draw.textlength(time_str, font=font)
                        x = (128 - text_width) // 2
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
                                draw.text(
                                    (x, y),
                                    time_str,
                                    font=font,
                                    fill="white" if blink_state else 0,
                                )
                        else:
                            draw.text((x, y), time_str, font=font, fill="white")
                self._post_write_sleep()
                break
            except OSError:
                if attempt < max_attempts - 1:
                    self._init_oled()
                    self._post_write_sleep()
                else:
                    self.device = None

    def show_date_view(
        self, day_str: str, date_str: str, options: list[str], selected_index: int
    ) -> None:
        """Affiche le jour en haut, la date en dessous, et les options horizontales en bas."""
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
                    # Affiche le jour en haut
                    day_width = draw.textlength(day_str, font=font_date)
                    day_x = (128 - day_width) // 2
                    draw.text((day_x, 5), day_str, font=font_date, fill="white")
                    # Affiche la date en dessous
                    date_width = draw.textlength(date_str, font=font_date)
                    date_x = (128 - date_width) // 2
                    draw.text((date_x, 25), date_str, font=font_date, fill="white")
                    # Affiche les options horizontales en bas
                    font_opt = self.fonts["menu"]
                    x_positions = [10, 70]
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
            except OSError:
                if attempt < max_attempts - 1:
                    self._init_oled()
                    self._post_write_sleep()
                else:
                    self.device = None

    def clear(self) -> None:
        """Efface l'écran."""
        if not self.device:
            self._init_oled()
            if not self.device:
                return
        try:
            with canvas(self.device) as draw:
                if self.device:
                    draw.rectangle(
                        (0, 0, self.device.width, self.device.height), fill=0
                    )
            self._post_write_sleep()
        except OSError:
            self._init_oled()

    def _reset_oled(self) -> None:
        """Réinitialise l'OLED (compatibilité avec les versions précédentes)."""
        self._init_oled()
