from src.components.i2c import I2C


class RTC:
    """Gère le DS3231 pour l'heure et les alarmes."""

    TIME_REG = 0x00
    ALARM1_REG = 0x07
    ALARM2_REG = 0x0B
    CONTROL_REG = 0x0E
    STATUS_REG = 0x0F
    DAY_OF_WEEK_REG = 0x03
    DATE_REG = 0x04
    MONTH_REG = 0x05
    YEAR_REG = 0x06

    def __init__(self, i2c: I2C, config: dict):
        self.i2c = i2c
        self.address = config["rtc_address"]
        self._enable_alarms()

    def _bcd_to_decimal(self, bcd: int) -> int:
        """Convertit BCD en décimal."""
        return (bcd & 0x0F) + ((bcd >> 4) * 10)

    def _decimal_to_bcd(self, decimal: int) -> int:
        """Convertit décimal en BCD."""
        return ((decimal // 10) << 4) | (decimal % 10)

    def _enable_alarms(self) -> None:
        """Active les interruptions d'alarmes."""
        try:
            control = self.i2c.read_byte_data(self.address, self.CONTROL_REG)
            control |= 0x03  # Activer A1IE et A2IE
            self.i2c.write_byte_data(self.address, self.CONTROL_REG, control)
        except Exception as e:
            print(f"Erreur activation alarmes RTC : {e}")

    def read_time(self) -> tuple[int, int]:
        """Lit l'heure (heures, minutes)."""
        try:
            data = self.i2c.read_block(self.address, self.TIME_REG, 3)
            if not data:  # Vérifie liste vide
                raise OSError("Lecture I2C vide")
            hours = self._bcd_to_decimal(data[2] & 0x3F)  # Masque pour mode 24h
            minutes = self._bcd_to_decimal(data[1] & 0x7F)
            if 0 <= hours < 24 and 0 <= minutes < 60:
                return hours, minutes
            return 0, 0
        except Exception as e:
            print(f"Erreur lecture heure RTC : {e}")
            return 0, 0

    def set_time(self, hours: int, minutes: int) -> None:
        """Règle l'heure."""
        try:
            data = [
                self._decimal_to_bcd(0),  # Secondes
                self._decimal_to_bcd(minutes),
                self._decimal_to_bcd(hours),
            ]
            for i, value in enumerate(data):
                self.i2c.write_byte(self.address, self.TIME_REG + i, value)
        except Exception as e:
            print(f"Erreur réglage heure RTC : {e}")

    def read_alarm(self, alarm_number: int) -> tuple[int, int, bool]:
        """Lit une alarme (heures, minutes, activée)."""
        try:
            control = self.i2c.read_byte_data(self.address, self.CONTROL_REG)
            status = self.i2c.read_byte_data(self.address, self.STATUS_REG)
            if alarm_number == 1:
                minute = self._bcd_to_decimal(
                    self.i2c.read_byte_data(self.address, self.ALARM1_REG + 1) & 0x7F
                )
                hour = self._bcd_to_decimal(
                    self.i2c.read_byte_data(self.address, self.ALARM1_REG + 2) & 0x3F
                )
                enabled = bool(control & 0x01) and not (status & 0x01)
            else:
                minute = self._bcd_to_decimal(
                    self.i2c.read_byte_data(self.address, self.ALARM2_REG) & 0x7F
                )
                hour = self._bcd_to_decimal(
                    self.i2c.read_byte_data(self.address, self.ALARM2_REG + 1) & 0x3F
                )
                enabled = bool(control & 0x02) and not (status & 0x02)
            return hour, minute, enabled
        except Exception as e:
            print(f"Erreur lecture alarme RTC : {e}")
            return 0, 0, False

    def set_alarm(
        self, alarm_number: int, hour: int, minute: int, enabled: bool
    ) -> None:
        """Règle une alarme."""
        try:
            if alarm_number == 1:
                self.i2c.write_byte(
                    self.address, self.ALARM1_REG, self._decimal_to_bcd(0)
                )
                self.i2c.write_byte(
                    self.address, self.ALARM1_REG + 1, self._decimal_to_bcd(minute)
                )
                self.i2c.write_byte(
                    self.address, self.ALARM1_REG + 2, self._decimal_to_bcd(hour)
                )
                self.i2c.write_byte(self.address, self.ALARM1_REG + 3, 0x80)
            else:
                self.i2c.write_byte(
                    self.address, self.ALARM2_REG, self._decimal_to_bcd(minute)
                )
                self.i2c.write_byte(
                    self.address, self.ALARM2_REG + 1, self._decimal_to_bcd(hour)
                )
                self.i2c.write_byte(self.address, self.ALARM2_REG + 2, 0x80)
            control = self.i2c.read_byte_data(self.address, self.CONTROL_REG)
            status = self.i2c.read_byte_data(self.address, self.STATUS_REG)
            if enabled:
                control |= 1 << (alarm_number - 1)
            else:
                control &= ~(1 << (alarm_number - 1))
            status &= ~(1 << (alarm_number - 1))
            self.i2c.write_byte_data(self.address, self.CONTROL_REG, control)
            self.i2c.write_byte_data(self.address, self.STATUS_REG, status)
        except Exception as e:
            print(f"Erreur réglage alarme RTC : {e}")

    def read_dow(self) -> int:
        """Lit le jour de la semaine (1=Dimanche, 7=Samedi)."""
        try:
            dow = self.i2c.read_byte_data(self.address, self.DAY_OF_WEEK_REG)
            return dow & 0x07  # Masque pour obtenir bits 0-2 (1-7)
        except Exception as e:
            print(f"Erreur lecture jour de la semaine RTC : {e}")
            return 1  # Défaut dimanche

    def read_date(self) -> tuple[int, int, int, int]:
        """Lit la date (année, mois, jour, jour de la semaine)."""
        try:
            dow = self.i2c.read_byte_data(self.address, self.DAY_OF_WEEK_REG) & 0x07
            date = self._bcd_to_decimal(
                self.i2c.read_byte_data(self.address, self.DATE_REG) & 0x3F
            )
            month = self._bcd_to_decimal(
                self.i2c.read_byte_data(self.address, self.MONTH_REG) & 0x1F
            )
            year = 2000 + self._bcd_to_decimal(
                self.i2c.read_byte_data(self.address, self.YEAR_REG)
            )
            return year, month, date, dow
        except Exception as e:
            print(f"Erreur lecture date RTC : {e}")
            return 2000, 1, 1, 1

    def set_date(self, year: int, month: int, date: int, dow: int) -> None:
        """Règle la date (année, mois, jour, jour de la semaine)."""
        try:
            data = [
                dow & 0x07,  # Binaire 1-7
                self._bcd_to_decimal(date),
                self._bcd_to_decimal(month),
                self._bcd_to_decimal(year - 2000),
            ]
            for i, value in enumerate(data):
                self.i2c.write_byte(self.address, self.DAY_OF_WEEK_REG + i, value)
        except Exception as e:
            print(f"Erreur réglage date RTC : {e}")
