import smbus2
import time


class I2C:
    """Gère le bus I2C du réveil."""

    def __init__(self, config: dict):
        self.port = config["port"]
        self.retries = config["retries"]
        self.retry_delay = config["retry_delay"]
        self.bus = None
        self._init_bus()

    def _init_bus(self) -> None:
        """Initialise le bus I2C."""
        try:
            if self.bus:
                self.bus.close()
        except (AttributeError, OSError):
            pass
        try:
            self.bus = smbus2.SMBus(self.port)
        except OSError as e:
            print(f"Erreur initialisation I2C : {e}")
            raise

    def read_block(self, address: int, register: int, length: int) -> list:
        """Lit un bloc de données I2C."""
        for attempt in range(self.retries):
            try:
                return self.bus.read_i2c_block_data(address, register, length)
            except OSError as e:
                if attempt < self.retries - 1:
                    time.sleep(self.retry_delay)
                    self._init_bus()
                else:
                    print(f"Échec lecture I2C après {self.retries} tentatives : {e}")
                    raise

    def write_byte(self, address: int, register: int, value: int) -> None:
        """Écrit un octet I2C."""
        for attempt in range(self.retries):
            try:
                self.bus.write_byte_data(address, register, value)
                return
            except OSError as e:
                if attempt < self.retries - 1:
                    time.sleep(self.retry_delay)
                    self._init_bus()
                else:
                    print(f"Échec écriture I2C après {self.retries} tentatives : {e}")
                    raise

    def read_byte_data(self, address, register):
        """Lit un octet à un registre spécifique sur l'adresse I2C."""
        return self.bus.read_byte_data(address, register)

    def write_byte_data(self, address, register, value):
        """Écrit un octet à un registre spécifique sur l'adresse I2C."""
        self.bus.write_byte_data(address, register, value)

    def close(self) -> None:
        """Ferme le bus I2C."""
        try:
            if self.bus:
                self.bus.close()
        except (AttributeError, OSError):
            pass
