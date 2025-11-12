import subprocess


class MusicControls:
    """Gère les commandes MPD (next/prev/pause/stop) de manière centralisée."""

    def __init__(self, audio_manager):
        self.audio_manager = audio_manager  # Pour stop intégré

    def next_track(self) -> bool:
        """Passe au morceau suivant ; retourne True si succès."""
        try:
            result = subprocess.run(
                ["mpc", "next"], capture_output=True, check=True, text=True
            )
            return result.returncode == 0
        except subprocess.CalledProcessError:
            return False

    def prev_track(self) -> bool:
        """Passe au morceau précédent ; retourne True si succès."""
        try:
            result = subprocess.run(
                ["mpc", "prev"], capture_output=True, check=True, text=True
            )
            return result.returncode == 0
        except subprocess.CalledProcessError:
            return False

    def pause_toggle(self) -> bool:
        """Toggle lecture/pause avec état explicite."""
        try:
            # Lit l'état actuel
            status = subprocess.check_output(["mpc", "status"]).decode()

            if "[playing]" in status:
                cmd = ["mpc", "pause"]  # Met en pause
            else:
                cmd = ["mpc", "play"]  # Reprend

            subprocess.run(cmd, capture_output=True, check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def stop(self) -> None:
        """Arrête la lecture (délégué à AudioManager pour cleanup)."""
        self.audio_manager.stop()
