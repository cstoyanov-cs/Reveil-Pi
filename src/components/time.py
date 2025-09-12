from src.components.rtc import RTC

class Time:
    """Gère l'heure et DST du réveil."""
    def __init__(self, rtc: RTC):
        self.rtc = rtc
        self.dst_enabled = False

    def get_time(self) -> str:
        """Retourne l'heure au format HH:MM."""
        hours, minutes = self.rtc.read_time()
        if self.dst_enabled:
            hours = (hours + 1) % 24
        return f"{hours:02d}:{minutes:02d}"

    def set_time(self, hours: int, minutes: int) -> None:
        """Règle l'heure."""
        if self.dst_enabled:
            hours = (hours - 1) % 24
        self.rtc.set_time(hours, minutes)

    def toggle_dst(self) -> None:
        """Bascule le mode DST."""
        self.dst_enabled = not self.dst_enabled