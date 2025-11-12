from typing import Union
import subprocess
import time
import os
import re
import signal
from typing import Any
import logging

logger = logging.getLogger(__name__)


class AudioManager:
    """Gère la lecture audio (SD/webradio) via MPD systemd."""

    def __init__(self, music_dir: str, webradio_stations: list):
        # Initialisation : répertoire musique et stations webradio (ligne ~15)
        self.music_dir = music_dir
        self.webradio_stations = webradio_stations
        self.music_playing = False
        self.play_mode: Union[str, None] = None
        self.current_station_name: Union[str, None] = None
        # Monitoring MPD : compteurs et timers pour recovery (ligne ~25)
        self.mpd_last_check = 0
        self.mpd_check_interval = 5.0
        self.mpd_restart_attempts = 0
        self.mpd_max_restarts = 3
        self.mpd_degraded_mode = False
        self.activating_since = 0.0
        # Timer pour reset mode dégradé
        self.degraded_since = 0
        self.degraded_log_throttle = 0  # Pour logs skippés sans spam
        self.degraded_reset_delay = 10.0
        self.mpd_unavailable = False  # Flag pour icône down
        # Vérification startup MPD (non-bloquante)
        startup_ok = self._startup_mpd()
        if not startup_ok:
            logger.warning("[WARN] MPD indisponible au démarrage - Mode recovery actif")
        else:
            logger.warning("[AUDIO] MPD startup OK - Prêt pour utilisation")

    def get_current_volume(self) -> float:
        """Retourne niveau volume MPD actuel (0.0-1.0). (ligne ~50)"""
        # Vérification volume via mpc
        try:
            output = (
                subprocess.check_output(
                    ["mpc", "volume"], timeout=1.0, stderr=subprocess.PIPE
                )
                .decode()
                .strip()
            )
            # Parse : "volume: 50%" → 0.5
            match = re.search(r"volume:\s*(\d+)%", output)
            if match:
                vol = int(match.group(1)) / 100.0
                return vol
            logger.warning(f"[AUDIO] get_volume: format inattendu '{output}'")
            return 1.0  # Défaut safe
        except subprocess.TimeoutExpired:
            logger.error("[AUDIO] Timeout get_volume (mpc volume)")
            return 1.0
        except Exception as e:
            logger.error(f"[AUDIO] Erreur get_volume: {e}")
            return 1.0

    def set_volume(self, level: float) -> None:
        """
        Règle le volume MPD (0.0-1.0).
        Utilise 'mpc volume' pour contrôle interne MPD, indépendant du système. (ligne ~70)
        """
        if not 0 <= level <= 1:
            logger.warning(f"[AUDIO] Niveau volume invalide: {level}")
            return
        vol_int = int(level * 100)  # MPD : 0-100
        try:
            # Commande MPD directe
            result = subprocess.run(
                ["mpc", "volume", str(vol_int)],
                check=True,
                capture_output=True,
                timeout=2.0,
            )
            if result.returncode != 0:
                logger.warning(f"[AUDIO] mpc volume échoué (rc={result.returncode})")
            # Confirmation avec délai (MPD peut lag)
            time.sleep(0.1)
            actual = self.get_current_volume()
            # Alerte si écart >5% (signe de problème MPD)
            if abs(actual - level) > 0.05:
                logger.warning(
                    f"[AUDIO] Écart volume ! demandé={level * 100:.0f}% "
                    f"mais MPD à {actual * 100:.0f}%"
                )
        except subprocess.CalledProcessError as e:
            logger.error(
                f"[AUDIO] Échec mpc volume (rc={e.returncode}): "
                f"{e.stderr.decode().strip()}"
            )
        except Exception as e:
            logger.error(f"[AUDIO] Erreur set_volume: {e}")

    def _is_mpd_running(self) -> bool:
        """Vérifie si MPD est actif (systemd + communication mpc). (ligne ~100)"""
        # Phase 1 : Check systemd
        try:
            current_time: float = time.time()
            systemctl_result = subprocess.run(
                ["systemctl", "is-active", "mpd.service"],
                capture_output=True,
                timeout=1.0,
                check=False,
            )
            service_stdout: str = systemctl_result.stdout.decode().strip()
            # Gestion état "activating" (démarrage en cours)
            if service_stdout == "activating":
                # Timer pour phases de démarrage
                if self.activating_since == 0.0:
                    self.activating_since = current_time
                elapsed: float = current_time - self.activating_since
                # Phase 1 : Grâce (0-10s) - Skip mpc
                if elapsed < 10.0:
                    return True
                # Phase 2 : Vérif (10-30s) - Accepte "activating" + check mpc
                elif elapsed <= 30.0:
                    service_active: bool = True  # Accepte état
                # Phase 3 : Timeout (>30s) - DOWN
                else:
                    logger.warning(
                        f"[MPD] Timeout activation ({elapsed:.1f}s > 30s) → Traité comme DOWN"
                    )
                    service_active = False
                    self.activating_since = 0.0
                    self.mpd_unavailable = True
                    return False
            # État normal (active/inactive/failed)
            else:
                if self.activating_since > 0.0:
                    self.activating_since = 0.0
                service_active = (
                    systemctl_result.returncode == 0 and service_stdout == "active"
                )
                if not service_active and "inactive" in service_stdout.lower():
                    self.mpd_unavailable = True
                elif service_active:
                    self.mpd_unavailable = False
            # Phase 2 : Check mpc (timeout variable)
            mpc_timeout: float = 5.0 if service_stdout == "activating" else 2.0
            mpc_result = subprocess.run(
                ["mpc", "status"],
                capture_output=True,
                timeout=mpc_timeout,
                check=False,
            )
            if mpc_result.returncode not in [0, 1]:
                logger.warning(
                    f"[MPD] mpc status inattendu (rc={mpc_result.returncode})"
                )
            mpc_ok: bool = mpc_result.returncode in [0, 1]
            # Détection "Connection refused"
            if (
                "Connection refused" in mpc_result.stderr.decode()
                or "Connection refused" in mpc_result.stdout.decode()
            ):
                mpc_ok = False
                logger.warning("[MPD] Détection 'Connection refused' → MPD down")
            # Résultat final
            if service_stdout == "activating":
                result: bool = mpc_ok
            else:
                result = service_active and mpc_ok
            if not result:
                logger.warning(
                    f"[MPD] Check failed → service_active={service_active}, "
                    f"mpc_ok={mpc_ok}, état='{service_stdout}'"
                )
            return result
        except subprocess.TimeoutExpired as e:
            logger.error(f"[MPD] Timeout lors du check: {e}")
            return False
        except Exception as e:
            logger.error(f"[MPD] Erreur inattendue dans check: {e}", exc_info=True)
            return False

    def _is_mpd_playing(self) -> bool:
        """Vérifie si MPD est en lecture (PLAY). (ligne ~170)"""
        try:
            output = subprocess.check_output(
                ["mpc", "status"], stderr=subprocess.PIPE, timeout=2.0
            ).decode()
            playing = "[playing]" in output
            return playing
        except subprocess.TimeoutExpired:
            logger.warning("[MPD] Timeout _is_mpd_playing")
            return False
        except Exception as e:
            logger.error(f"[MPD] Erreur _is_mpd_playing: {e}")
            return False

    def _startup_mpd(self) -> bool:
        """
        Vérif rapide MPD au boot (non-bloquante).
        Si down, systemd le gère en fond ; vrai check plus tard. (ligne ~190)
        """
        try:
            mpc_result = subprocess.run(
                ["mpc", "status"],
                capture_output=True,
                timeout=2.0,
                check=False,
            )
            if mpc_result.returncode not in [0, 1]:
                logger.warning(
                    f"[MPD] Startup mpc inattendu (rc={mpc_result.returncode})"
                )
            if mpc_result.returncode in [0, 1]:
                return True
            return False
        except subprocess.TimeoutExpired:
            return False
        except Exception as e:
            logger.warning(f"[MPD] Check startup: {e}")
            return False

    def _ensure_mpd(self) -> bool:
        """
        Assure MPD systemd actif (lance si besoin).
        Ne lance jamais d'instance locale. (ligne ~220)
        """
        if self._is_mpd_running():
            return True
        try:
            # Start via systemd (sans assignation, check=True suffit)
            subprocess.run(
                ["sudo", "systemctl", "start", "mpd.service"],
                timeout=5.0,
                check=True,
                capture_output=True,
            )
            # Attente démarrage (max 5s)
            for attempt in range(10):
                time.sleep(0.5)
                if self._is_mpd_running():
                    logger.info(f"[OK] MPD démarré après {(attempt + 1) * 0.5:.1f}s")
                    return True
            logger.error("[ERROR] MPD timeout après 5s")
            return False
        except subprocess.CalledProcessError as e:
            logger.error(
                f"[ERROR] Impossible de démarrer MPD: rc={e.returncode}, stderr='{e.stderr.decode().strip()}'"
            )
            return False
        except Exception as e:
            logger.error(f"[ERROR] Erreur MPD systemd: {e}")
            return False

    def _prepare_mpd(self, shuffle: bool = False) -> bool:
        """Prépare MPD pour lecture (stop/clear + random/repeat). (ligne ~250)"""
        if not self._ensure_mpd():
            logger.error("[MPD] _ensure_mpd échoué → abort prepare")
            return False
        # Stabilisation post-démarrage
        time.sleep(0.5)
        # Re-check avec retry (3 tentatives)
        for attempt in range(3):
            if self._is_mpd_running():
                break
            if attempt < 2:
                time.sleep(0.5)
        else:
            logger.warning("[MPD] MPD instable après ensure → abort")
            return False
        try:
            # Stop et clear
            for cmd in ["stop", "clear"]:
                result = subprocess.run(
                    ["mpc", "-q", cmd], timeout=2.0, check=False, capture_output=True
                )
                if result.returncode != 0:
                    logger.warning(
                        f"[MPD] {cmd} failed (code {result.returncode}): {result.stderr.decode().strip()}"
                    )
                    return False
            # Settings random/repeat
            random_cmd = "on" if shuffle else "off"
            result = subprocess.run(
                ["mpc", "-q", "random", random_cmd],
                timeout=2.0,
                check=False,
                capture_output=True,
            )
            if result.returncode != 0:
                logger.warning(
                    f"[MPD] random {random_cmd} failed (code {result.returncode})"
                )
                return False
            result = subprocess.run(
                ["mpc", "-q", "repeat", "on"],
                timeout=2.0,
                check=False,
                capture_output=True,
            )
            if result.returncode != 0:
                logger.warning(f"[MPD] repeat on failed (code {result.returncode})")
                return False
            return True
        except subprocess.TimeoutExpired as e:
            logger.error(f"[MPD] Timeout prepare: {e}")
            return False
        except Exception as e:
            logger.error(f"[ERROR] Préparation MPD: {e}")
            return False

    def play_random_music(self) -> bool:
        """Lance lecture aléatoire de toute la bibliothèque. (ligne ~310)"""
        success = self.play_folder(self.music_dir, shuffle=True)
        if success:
            pass
        else:
            logger.error("[AUDIO] Échec play_random_music")
        return success

    def play_folder(self, folder_path: str, shuffle: bool = False) -> bool:
        """Joue un dossier (récursif) avec shuffle on/off. (ligne ~320)"""
        if not os.path.exists(folder_path):
            logger.error(f"[ERROR] Dossier {folder_path} inexistant")
            return False
        try:
            if not self.ensure_mpd_available():
                logger.warning(
                    "[AUDIO] MPD down au play_folder → Restart tenté, mais abort si fail"
                )
                return False  # Abort play si toujours down
            if not self._prepare_mpd(shuffle=shuffle):
                logger.error("[AUDIO] _prepare_mpd échoué → abort play_folder")
                return False
            # Chemin relatif pour MPD
            if folder_path == self.music_dir:
                rel_path = "/"
            else:
                rel_path = os.path.relpath(folder_path, self.music_dir)
            add_result = subprocess.run(
                ["mpc", "add", rel_path], timeout=3.0, check=True, capture_output=True
            )
            if add_result.returncode != 0:
                logger.warning(f"[AUDIO] mpc add échoué (rc={add_result.returncode})")
            play_result = subprocess.run(
                ["mpc", "play"], timeout=2.0, check=True, capture_output=True
            )
            if play_result.returncode != 0:
                logger.warning(f"[AUDIO] mpc play échoué (rc={play_result.returncode})")
            time.sleep(0.5)
            self.music_playing = self._is_mpd_playing()
            self.play_mode = "local"
            self.current_station_name = None
            return self.music_playing
        except subprocess.CalledProcessError as e:
            logger.error(
                f"[ERROR] Play folder: rc={e.returncode}, stderr='{e.stderr.decode().strip()}'"
            )
            return False
        except Exception as e:
            logger.error(f"[ERROR] Play folder inattendu: {e}")
            return False

    def play_file_sequential(self, file_path: str, folder_path: str) -> bool:
        """Joue fichier spécifique + suivants dans ordre naturel. (ligne ~370)"""
        if not os.path.exists(folder_path):
            logger.error(f"[ERROR] Dossier {folder_path} inexistant")
            return False
        if not os.path.isfile(file_path):
            logger.error(f"[ERROR] Fichier {file_path} invalide")
            return False
        try:
            if not self.ensure_mpd_available():
                logger.warning(
                    "[AUDIO] MPD down au play_file_sequential → Restart tenté, mais abort si fail"
                )
                return False
            if not self._prepare_mpd(shuffle=False):
                logger.error("[AUDIO] _prepare_mpd échoué → abort sequential")
                return False

            # Repeat OFF pour fin dossier
            repeat_result = subprocess.run(
                ["mpc", "repeat", "off"], timeout=2.0, check=True, capture_output=True
            )
            if repeat_result.returncode != 0:
                logger.warning(
                    f"[AUDIO] mpc repeat off échoué (rc={repeat_result.returncode})"
                )

            # Normaliser chemins
            file_path = os.path.normpath(os.path.abspath(file_path))
            folder_path = os.path.normpath(os.path.abspath(folder_path))

            # Vérif
            if not os.path.isfile(file_path) or not os.path.exists(folder_path):
                logger.error(
                    f"[AUDIO] Fichier '{file_path}' ou dossier '{folder_path}' invalide"
                )
                return False

            # Lister et trier fichiers (absolus)
            all_files = [
                os.path.normpath(os.path.abspath(os.path.join(folder_path, f)))
                for f in os.listdir(folder_path)
                if os.path.isfile(os.path.join(folder_path, f))
            ]
            all_files.sort()
            if file_path not in all_files:
                logger.error("[AUDIO] Fichier non trouvé dans le dossier")
                return False

            # Index start
            start_index = all_files.index(file_path)
            ordered_files = all_files  # Tous les fichiers du dossier
            play_track_number = start_index + 1  # Position MPD (1-indexed)
            logger.info(
                f"[AUDIO] Ajout {len(ordered_files)} fichiers depuis index {start_index}"
            )

            # 🔥 PHASE 1 : Tentative ajout TOUS les fichiers (sans rescan)
            failed_files = []  # Liste des fichiers non indexés

            for i, file in enumerate(ordered_files):
                filename = os.path.basename(file)
                rel_file = os.path.relpath(file, self.music_dir)

                add_result = subprocess.run(
                    ["mpc", "add", rel_file],
                    timeout=2.0,
                    check=False,
                    capture_output=True,
                )

                if add_result.returncode != 0:
                    stderr = (
                        add_result.stderr.decode().strip() if add_result.stderr else ""
                    )

                    # Si erreur DB → Mémoriser pour rescan
                    if "no such" in stderr.lower() or "not found" in stderr.lower():
                        failed_files.append((file, rel_file, filename))
                        logger.warning(f"[AUDIO] '{filename}' non indexé (détecté)")
                    else:
                        # Autre erreur (format, permission...) → Log mais continue
                        logger.warning(
                            f"[AUDIO] Skip '{filename}' (rc={add_result.returncode}): {stderr}"
                        )

                if i % 5 == 0 and i > 0:  # Log throttle
                    logger.info(f"[AUDIO] Traité {i + 1}/{len(ordered_files)}")

            # 🔥 PHASE 2 : Si échecs détectés → Rescan PUIS retry
            if failed_files:
                logger.warning(
                    f"[AUDIO] {len(failed_files)} fichier(s) non indexé(s) → Rescan dossier '{folder_path}'"
                )

                # Rescan uniquement du dossier ciblé
                # ✅ APRÈS : Gestion cas racine
                rel_folder = os.path.relpath(folder_path, self.music_dir)

                # Si dossier racine, rescan complet (sans argument)
                if rel_folder == "." or rel_folder == "":
                    logger.info("[AUDIO] Rescan complet de la bibliothèque")
                    update_cmd = ["mpc", "update"]
                else:
                    logger.info(f"[AUDIO] Rescan ciblé du dossier '{rel_folder}'")
                    update_cmd = ["mpc", "update", rel_folder]

                update_result = subprocess.run(
                    update_cmd,
                    timeout=30.0,
                    check=False,
                    capture_output=True,
                )

                if update_result.returncode != 0:
                    update_stderr = (
                        update_result.stderr.decode().strip()
                        if update_result.stderr
                        else ""
                    )
                    logger.error(
                        f"[AUDIO] Rescan échoué (rc={update_result.returncode}): {update_stderr}"
                    )
                    return False

                # ⏳ Attente indexation active
                logger.info("[AUDIO] Indexation en cours...")
                max_wait = 40  # 40 × 0.5s = 20s max
                for i in range(max_wait):
                    time.sleep(0.5)
                    status = subprocess.run(
                        ["mpc", "status"],
                        capture_output=True,
                        timeout=2.0,
                        check=False,
                    )
                    output = status.stdout.decode()
                    if "Updating" not in output:
                        logger.info(
                            f"[AUDIO] Indexation terminée après {(i + 1) * 0.5:.1f}s"
                        )
                        break
                else:
                    logger.warning(
                        f"[AUDIO] Timeout indexation après {max_wait * 0.5}s"
                    )

                # ✅ Retry fichiers échoués
                still_failed = []
                for file, rel_file, filename in failed_files:
                    retry_add = subprocess.run(
                        ["mpc", "add", rel_file],
                        timeout=2.0,
                        check=False,
                        capture_output=True,
                    )

                    if retry_add.returncode != 0:
                        still_failed.append(filename)
                        logger.error(
                            f"[AUDIO] '{filename}' échoue même après rescan (rc={retry_add.returncode})"
                        )
                    else:
                        logger.info(f"[AUDIO] ✅ '{filename}' ajouté après rescan")

                if still_failed:
                    logger.error(
                        f"[AUDIO] {len(still_failed)} fichier(s) définitivement inaccessible(s): {still_failed}"
                    )
                    # Continue quand même si au moins 1 fichier OK

            # 🎵 PHASE 3 : Vérifier playlist non vide puis play
            playlist_check = subprocess.run(
                ["mpc", "playlist"],
                capture_output=True,
                timeout=2.0,
                check=False,
            )

            playlist_count = len(playlist_check.stdout.decode().strip().split("\n"))

            if playlist_count == 0 or (
                playlist_count == 1 and not playlist_check.stdout.decode().strip()
            ):
                logger.error("[AUDIO] Aucun fichier ajouté à la playlist → Abort")
                return False

            logger.info(f"[AUDIO] Playlist prête avec {playlist_count} fichier(s)")

            # Play
            play_result = subprocess.run(
                ["mpc", "play", str(play_track_number)],
                timeout=2.0,
                check=True,
                capture_output=True,
            )
            if play_result.returncode != 0:
                logger.warning(
                    f"[AUDIO] mpc play 1 échoué (rc={play_result.returncode})"
                )
                return False

            time.sleep(0.5)
            self.music_playing = self._is_mpd_playing()
            self.play_mode = "local"
            self.current_station_name = None
            logger.info(
                f"[AUDIO] play_file_sequential terminé: {playlist_count} fichiers, playing={self.music_playing}"
            )
            return self.music_playing

        except Exception as e:
            logger.error(f"[ERROR] Play sequential: {e}")
            return False

    def play_webradio_station(self, index: int) -> bool:
        """Joue une station webradio. (ligne ~440)"""
        if index >= len(self.webradio_stations):
            logger.error(f"[ERROR] Index webradio invalide: {index}")
            return False
        station = self.webradio_stations[index]
        self.play_mode = "webradio"
        self.current_station_name = station["name"]
        try:
            if not self.ensure_mpd_available():
                logger.warning(
                    "[AUDIO] MPD down au play_webradio → Restart tenté, mais abort si fail"
                )
                return False
            if not self._prepare_mpd(shuffle=False):
                logger.error("[AUDIO] _prepare_mpd échoué → abort webradio")
                return False
            add_result = subprocess.run(
                ["mpc", "add", station["url"]],
                timeout=3.0,
                check=True,
                capture_output=True,
            )
            if add_result.returncode != 0:
                logger.warning(
                    f"[AUDIO] mpc add URL échoué (rc={add_result.returncode})"
                )
            play_result = subprocess.run(
                ["mpc", "play"], timeout=2.0, check=True, capture_output=True
            )
            if play_result.returncode != 0:
                logger.warning(f"[AUDIO] mpc play échoué (rc={play_result.returncode})")
            time.sleep(2.0)  # Buffer réseau
            self.music_playing = self._is_mpd_playing()
            return self.music_playing
        except subprocess.CalledProcessError as e:
            logger.error(
                f"[ERROR] Webradio {station['name']}: rc={e.returncode}, stderr='{e.stderr.decode().strip()}'"
            )
            return False
        except Exception as e:
            logger.error(f"[ERROR] Webradio inattendu: {e}")
            return False

    def _reset_play_state(self) -> None:
        """Réinitialise l'état de lecture. (ligne ~480)"""
        self.play_mode = None
        self.current_station_name = None
        self.music_playing = False

    def get_detailed_track_info(self) -> dict:
        """
        Infos détaillées morceau : artist, title, temps, progression.
        Structure dict pour UI. (ligne ~490)
        """
        if not self.music_playing or self.play_mode is None:
            return {
                "artist": "Inconnu",
                "title": "Inconnu",
                "elapsed": "0:00",
                "total": "0:00",
                "progress": 0.0,
                "is_playing": False,
                "source": None,
            }
        try:
            # Artiste
            try:
                artist_output = (
                    subprocess.check_output(
                        ["mpc", "current", "--format", "%artist%"],
                        stderr=subprocess.PIPE,
                        timeout=1.0,
                    )
                    .decode()
                    .strip()
                )
                artist = artist_output if artist_output else "Inconnu"
            except Exception:
                artist = "Inconnu"
            # Titre
            try:
                title_output = (
                    subprocess.check_output(
                        ["mpc", "current", "--format", "%title%"],
                        stderr=subprocess.PIPE,
                        timeout=1.0,
                    )
                    .decode()
                    .strip()
                )
                title = title_output if title_output else "Inconnu"
            except Exception:
                title = "Inconnu"
            # Statut + temps
            status_output = subprocess.check_output(
                ["mpc", "status"], stderr=subprocess.PIPE, timeout=1.0
            ).decode()
            is_playing = "[playing]" in status_output
            # Webradio : streaming
            if self.play_mode == "webradio":
                time_match = re.search(r"(\d+:\d+)", status_output)
                elapsed = time_match.group(1) if time_match else "0:00"
                return {
                    "artist": self.current_station_name or "Webradio",
                    "title": title,
                    "elapsed": elapsed,
                    "total": "∞",
                    "progress": 0.0,
                    "is_playing": is_playing,
                    "source": "webradio",
                }
            # Local : progression
            time_match = re.search(
                r"(\d+:\d+(?:\.\d+)?)\s*/\s*(\d+:\d+(?:\.\d+)?)", status_output
            )
            if time_match:
                elapsed = time_match.group(1).split(".")[0]
                total = time_match.group(2).split(".")[0]

                def time_to_seconds(time_str: str) -> int:
                    parts = time_str.split(":")
                    if len(parts) == 2:
                        return int(parts[0]) * 60 + int(parts[1])
                    elif len(parts) == 3:
                        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                    return 0

                elapsed_sec = time_to_seconds(elapsed)
                total_sec = time_to_seconds(total)
                progress = elapsed_sec / total_sec if total_sec > 0 else 0.0
                return {
                    "artist": artist,
                    "title": title,
                    "elapsed": elapsed,
                    "total": total,
                    "progress": progress,
                    "is_playing": is_playing,
                    "source": "sd",
                }
            return {
                "artist": artist,
                "title": title,
                "elapsed": "0:00",
                "total": "0:00",
                "progress": 0.0,
                "is_playing": is_playing,
                "source": "sd",
            }
        except subprocess.TimeoutExpired:
            logger.error("[AUDIO] Timeout get_detailed_track_info")
            return {
                "artist": "Erreur",
                "title": "Erreur",
                "elapsed": "0:00",
                "total": "0:00",
                "progress": 0.0,
                "is_playing": False,
                "source": None,
            }
        except Exception as e:
            logger.error(f"[ERROR] get_detailed_track_info: {e}")
            return {
                "artist": "Erreur",
                "title": "Erreur",
                "elapsed": "0:00",
                "total": "0:00",
                "progress": 0.0,
                "is_playing": False,
                "source": None,
            }

    def ensure_mpd_available(self) -> bool:
        """
        Vérif/réparation MPD avec throttling (check 5s max).
        Reset dégradé auto après 60s. (ligne ~600)
        """
        current_time: float = time.time()
        # Throttle check
        if current_time - self.mpd_last_check < 5.0:
            return not self.mpd_degraded_mode
        self.mpd_last_check = current_time
        # Reset dégradé après 60s
        if self.mpd_degraded_mode:
            if current_time - self.degraded_since > 60.0:
                self.mpd_degraded_mode = False
                self.mpd_restart_attempts = 0
                self.degraded_since = 0
            else:
                return False
        # Health check
        try:
            mpd_ok: bool = self._check_mpd_health()
            if mpd_ok:
                self.mpd_degraded_mode = False
                self.mpd_unavailable = False
                self.mpd_restart_attempts = 0
                self.degraded_since = 0
            else:
                logger.warning("[MPD] Health check échoué")
            return mpd_ok
        except Exception as e:
            logger.error(f"[MPD] Exception health check: {e}")
            return False

    def _check_mpd_health(self) -> bool:
        """Vérif santé MPD + recovery si down. (ligne ~650)"""
        try:
            # Pre-check systemd
            if not self._is_mpd_running():
                logger.warning("[MPD] Service systemd down → Crash détecté")
                return self._attempt_recovery()
            # Test mpc
            result = subprocess.run(
                ["mpc", "status"], capture_output=True, timeout=2.0, check=False
            )
            stderr_msg = result.stderr.decode().strip()
            if stderr_msg:
                logger.error(
                    f"[MPD] Erreur mpc: '{stderr_msg}' (code={result.returncode})"
                )
            if result.returncode != 0:
                logger.warning(
                    f"[MPD] mpc status failed (rc={result.returncode}): {stderr_msg}"
                )
                raise subprocess.CalledProcessError(result.returncode, "mpc")
            # OK si rc 0/1
            if result.returncode in [0, 1]:
                self.mpd_restart_attempts = 0
                return True
            raise subprocess.CalledProcessError(result.returncode, "mpc")
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
            logger.warning(f"[MPD] Crash détecté : {e} → Tentative recovery")
            return self._attempt_recovery()

    def _attempt_recovery(self) -> bool:
        """Recovery MPD avec limite 3 tentatives ; timeout global 90s. (ligne ~680)"""
        if self.mpd_restart_attempts >= self.mpd_max_restarts:
            if self.degraded_since == 0:
                self.degraded_since = time.time()
            logger.error(
                f"[MPD] ⚠️ MODE DÉGRADÉ après {self.mpd_max_restarts} échecs (depuis {self.degraded_since})"
            )
            self.mpd_degraded_mode = True
            self.mpd_unavailable = True
            return False
        self.mpd_restart_attempts += 1
        logger.warning(
            f"[MPD] Tentative restart {self.mpd_restart_attempts}/{self.mpd_max_restarts}"
        )

        def timeout_handler(signum: int, frame: Any) -> None:
            logger.warning(f"[MPD] Timeout handler déclenché (signal {signum})")
            raise TimeoutError("Restart MPD timeout")

        try:
            signal.signal(signal.SIGALRM, timeout_handler)
            start_time = time.time()
            signal.alarm(90)
            result = self._restart_mpd()
            elapsed = time.time() - start_time
            signal.alarm(0)
            if result:
                logger.warning("[MPD] Recovery réussi")
                self.mpd_restart_attempts = 0
                return True
            logger.error(f"[MPD] ❌ Échec restart après {elapsed:.1f}s")
            return False
        except TimeoutError:
            logger.error("[MPD] ❌ Timeout restart (>90s)")
            signal.alarm(0)
            return False
        except Exception as e:
            logger.error(f"[MPD] ❌ Exception restart: {e}")
            signal.alarm(0)
            return False

    def _restart_mpd(self) -> bool:
        """Redémarre MPD via systemd (socket + service forcé). (ligne ~720)"""
        start_time = time.time()
        try:
            logger.warning("[MPD] Restart socket + service...")
            # Stop
            stop_result = subprocess.run(
                ["sudo", "systemctl", "stop", "mpd.service", "mpd.socket"],
                capture_output=True,
                timeout=5.0,
                check=False,
            )
            if stop_result.returncode != 0:
                logger.warning(f"[MPD] Stop incomplet (rc={stop_result.returncode})")
            time.sleep(1)  # Post-stop pour cleanup systemd
            # Start socket
            socket_result = subprocess.run(
                ["sudo", "systemctl", "start", "mpd.socket"],
                capture_output=True,
                timeout=15.0,
                check=True,
            )
            logger.info(f"[MPD] Socket démarré (returncode={socket_result.returncode})")
            # Start service explicite (fix clé : force activation)
            service_start = subprocess.run(
                ["sudo", "systemctl", "start", "mpd.service"],
                capture_output=True,
                timeout=5.0,
                check=False,  # Non fatal si déjà actif
            )
            if service_start.returncode != 0:
                logger.warning(
                    f"[MPD] Start service échoué (rc={service_start.returncode})"
                )
            time.sleep(1.0)  # Sync post-start
            # Attente service (max 60s)
            service_active: bool = False
            max_wait_attempts: int = 120
            for attempt in range(max_wait_attempts):
                service_result = subprocess.run(
                    ["systemctl", "is-active", "mpd.service"],
                    capture_output=True,
                    timeout=2.0,
                    check=False,
                )
                service_status: str = service_result.stdout.decode().strip()
                # Log status full throttlé (tous 10s) pour debug blocages
                if attempt % 20 == 0 and attempt > 0:
                    try:
                        full_status = subprocess.run(
                            ["systemctl", "status", "mpd.service", "--no-pager", "-l"],
                            capture_output=True,
                            timeout=3.0,
                            check=False,
                        )
                        status_lines = (
                            full_status.stdout.decode().strip().split("\n")[:3]
                        )
                        logger.info(
                            f"[MPD] Attente service ({attempt * 0.5:.1f}s) → status='{service_status}', "
                            f"détails: {', '.join([line.strip() for line in status_lines])}"
                        )
                    except Exception as e:
                        logger.warning(f"[MPD] Erreur status full: {e}")
                if service_status in ["active", "activating"]:
                    wait_time: float = (attempt + 1) * 0.5
                    service_active = True
                    break
                time.sleep(0.5)
            if not service_active:
                elapsed = time.time() - start_time
                logger.error(
                    f"[MPD] Service non actif après {max_wait_attempts * 0.5:.0f}s (total {elapsed:.1f}s)"
                )
                self.mpd_unavailable = True
                return False
            # Attente mpc (max 20s)
            max_mpc_attempts: int = 40
            for attempt in range(max_mpc_attempts):
                time.sleep(0.5)
                mpc_result = subprocess.run(
                    ["mpc", "status"],
                    capture_output=True,
                    timeout=3.0,
                    check=False,
                )
                if mpc_result.returncode in [0, 1]:
                    wait_time: float = (attempt + 1) * 0.5
                    total_elapsed = time.time() - start_time
                    logger.info(
                        f"[MPD] ✅ mpc répond après {wait_time:.1f}s (total {total_elapsed:.1f}s)"
                    )
                    return True
            total_elapsed = time.time() - start_time
            logger.error(
                f"[MPD] mpc timeout après {max_mpc_attempts * 0.5:.0f}s (total {total_elapsed:.1f}s)"
            )
            self.mpd_unavailable = True
            return False
        except subprocess.CalledProcessError as e:
            logger.error(
                f"[MPD] Erreur systemctl stop/start: rc={e.returncode}, stderr='{e.stderr.decode().strip()}'"
            )
            return False
        except subprocess.TimeoutExpired as e:
            logger.error(f"[MPD] Timeout commande systemctl: {e}")
            return False
        except Exception as e:
            logger.error(f"[MPD] Exception inattendue restart: {e}")
            return False

    def stop(self) -> None:
        """Arrête la lecture sans toucher au service MPD. (ligne ~820)"""
        self._reset_play_state()
        try:
            stop_result = subprocess.run(
                ["mpc", "stop"], timeout=2.0, check=True, capture_output=True
            )
            if stop_result.returncode != 0:
                logger.warning(f"[AUDIO] mpc stop échoué (rc={stop_result.returncode})")
        except subprocess.CalledProcessError as e:
            logger.warning(
                f"[ERROR] Arrêt lecture: rc={e.returncode}, stderr='{e.stderr.decode().strip()}'"
            )

    def cleanup(self) -> None:
        """
        Cleanup : stop lecture seulement.
        Préserve MPD systemd. (ligne ~840)
        """
        self.stop()
