import subprocess
import time
import os


class AudioManager:
    """Gère la lecture audio (SD/webradio) via MOCP."""

    def __init__(self, music_dir: str, webradio_stations: list):
        self.music_dir = music_dir  # Ex. "/home/reveil/Musique"
        self.webradio_stations = webradio_stations  # Liste depuis webradios.json
        self.music_playing = False

    def _is_moc_server_running(self) -> bool:
        """Vérifie si serveur MOC tourne."""
        try:
            subprocess.check_output(["pgrep", "-f", "mocp -S"], stderr=subprocess.PIPE)
            return True
        except subprocess.CalledProcessError:
            return False

    def _ensure_moc_server(self) -> bool:
        """Lance serveur MOC si absent."""
        if self._is_moc_server_running():
            return True
        try:
            subprocess.run(
                ["mocp", "-S"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"Erreur lancement MOC: {e}")
            return False

    def _start_moc_playback(self, add_cmd: list) -> bool:
        """Stop/clear/add/play générique ; retourne si PLAY."""
        try:
            if not self._ensure_moc_server():
                return False
            subprocess.run(
                ["mocp", "-s"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                ["mocp", "-c"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                add_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            subprocess.run(
                ["mocp", "-p"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            time.sleep(1)  # Délai init
            return self._is_moc_playing()
        except subprocess.CalledProcessError as e:
            print(f"Erreur playback MOC: {e}")
            return False

    def _is_moc_playing(self) -> bool:
        """Vérifie état PLAY."""
        try:
            output = subprocess.check_output(
                ["mocp", "-i"], stderr=subprocess.PIPE
            ).decode()
            return "State: PLAY" in output
        except subprocess.CalledProcessError:
            return False

    def play_random_music(self):
        """Joue une musique aléatoire du dossier Musique et les suivantes aléatoirement."""
        try:
            if not os.path.exists(self.music_dir):
                print(
                    f"[ERROR {time.time():.3f}] Le dossier {self.music_dir} n'existe pas."
                )
                return False

            # Terminer toute instance MOCP existante
            subprocess.run(["mocp", "-x"], capture_output=True, check=False)

            # Démarrer le serveur MOCP
            subprocess.run(["mocp", "-S"], capture_output=True, check=False)
            time.sleep(0.4)  # Délai pour laisser le serveur démarrer

            # Vider la playlist
            subprocess.run(["mocp", "-c"], capture_output=True, check=False)

            # Ajouter le dossier
            subprocess.Popen(
                ["mocp", "-a", "-r", self.music_dir], stdout=subprocess.PIPE
            )

            # Activer shuffle
            result = subprocess.run(
                ["mocp", "-o", "shuffle"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if result.stderr:
                print(
                    f"[ERROR {time.time():.3f}] Erreur mocp -o shuffle, stderr={result.stderr.decode()}"
                )

            # Lancer la lecture
            subprocess.Popen(["mocp", "-p"], stdout=subprocess.PIPE)

            self.music_playing = True
            return True

        except Exception as e:
            print(
                f"[ERROR {time.time():.3f}] Erreur lors de la lecture de la musique : {e}"
            )
            return False

    def play_webradio_station(self, index: int) -> bool:
        """Joue une station webradio via MOC, réutilise instance si fonctionnelle."""
        if index >= len(self.webradio_stations):
            print(f"[ERROR {time.time():.3f}] Index webradio invalide: {index}")
            return False

        url = self.webradio_stations[index]["url"]
        try:
            # Vérifie état actuel de MOC
            result = subprocess.run(
                ["mocp", "-i"], capture_output=True, text=True, timeout=3.0, check=False
            )
            current_state = None
            current_file = None
            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if line.startswith("State: "):
                        current_state = line.split(": ")[1]
                    if line.startswith("File: "):
                        current_file = line.split(": ")[1]

            # Si MOC joue déjà la bonne webradio, pas besoin de relancer
            if current_state == "PLAY" and current_file == url:
                self.music_playing = True
                return True

            # Si MOC est démarré mais pas en lecture ou mauvaise piste, vider playlist
            if current_state in ["PLAY", "PAUSE", "STOP"]:
                subprocess.run(
                    ["mocp", "-c"], capture_output=True, text=True, check=False
                )
            else:
                # MOC non démarré ou en erreur, relancer serveur
                subprocess.run(
                    ["pkill", "-f", "mocp"], capture_output=True, check=False
                )
                result = subprocess.run(
                    ["mocp", "-S"], capture_output=True, text=True, check=False
                )
                if result.returncode != 0:
                    print(
                        f"[ERROR {time.time():.3f}] Échec démarrage serveur MOC: {result.stderr}"
                    )
                    return False
                time.sleep(0.3)  # Délai pour stabiliser serveur

            # Ajoute URL et lance lecture
            result = subprocess.run(
                ["mocp", "-a", url], capture_output=True, text=True, check=False
            )
            if result.returncode != 0:
                print(
                    f"[ERROR {time.time():.3f}] Échec ajout webradio: {result.stderr}"
                )
                return False

            # Tente de démarrer lecture (3 retries)
            for _ in range(3):
                result = subprocess.run(
                    ["mocp", "-p"], capture_output=True, text=True, check=False
                )
                if result.returncode == 0:
                    self.music_playing = True
                    return True
                time.sleep(1.0)

            print(
                f"[ERROR {time.time():.3f}] Échec démarrage lecture après 3 tentatives"
            )
            return False

        except Exception as e:
            print(f"[ERROR {time.time():.3f}] Erreur play_webradio_station: {e}")
            return False

    def stop(self) -> None:
        if self.music_playing:
            try:
                result = subprocess.run(
                    ["mocp", "-s"], capture_output=True, check=False
                )
                if result.returncode not in [
                    0,
                    2,
                ]:  # Ignore 0 (OK) et 2 (pas en lecture/serveur inactif)
                    print(f"Erreur arrêt MOC: {result.stderr.decode()}")
            except Exception as e:
                print(f"Erreur inattendue arrêt MOC: {e}")
            self.music_playing = False
