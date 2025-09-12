```markdown
# Réveil Numérique Raspberry Pi

## Description
Ce projet est un réveil numérique basé sur un Raspberry Pi 2. Il affiche l'heure en temps réel, gère deux alarmes configurables, et joue de la musique via MOC (Music On Console) pour les réveils, avec un buzzer comme option de secours en cas de panne audio. L'interface utilisateur repose sur un encodeur rotatif pour naviguer dans des menus intuitifs affichés sur un écran OLED. Le système est alimenté par un UPS HAT avec batteries pour une autonomie accrue en cas de coupure de courant.

Le code Python est modulaire : il optimise les interruptions GPIO pour une réactivité fluide, utilise un cache pour l'heure afin de minimiser les lectures RTC, et inclut un mode veille pour économiser l'énergie. L'objectif est de fournir un réveil fiable et personnalisable, idéal pour un usage quotidien ou des projets DIY.

## Fonctionnalités Principales
- Affichage de l'heure et de la date sur écran OLED.
- Configuration de deux alarmes indépendantes (heure, minute, activation/désactivation).
- Lecture de musique via MOC pour les alarmes ; buzzer de secours si MOC échoue.
- Navigation intuitive via encodeur rotatif : rotation pour sélectionner, appui pour valider.
- Interrupteurs hardware pour activer/désactiver les alarmes manuellement.
- Stockage des alarmes sur le module RTC pour persistance même après redémarrage.
- Mode veille : écran éteint après inactivité, réactivé par interaction.
- Surveillance de l'alimentation via UPS HAT.

## Matériel Requis
- Raspberry Pi 2 (ou compatible).
- Écran OLED SH1106 (128x64 pixels).
- Module RTC DS3231 (I2C adresse 0x68, avec pile pour maintenir l'heure).
- Buzzer
- Encodeur rotatif KY-040.
- Raspberry DAC Pro pour sortie audio I2S.
- Amplificateur PAM8406 (stéréo, 3W par canal).
- Enceintes stéréo 3W 8Ω (x2).
- Waveshare Pi Hat UPS avec deux batteries 18650.
- Interrupteurs ON/OFF (x2) pour activer/désactiver les alarmes.
- Autres : boîtier en bois pour l'assemblage, cache pour enceintes.

**Note :** Les connexions GPIO spécifiques ne sont pas détaillées ici ; reportez-vous au code pour les pins utilisés

## Prérequis Logiciels
- Raspberry Pi OS Lite.
- Bibliothèques Python installées via pip :
  ```
  pip install smbus2 rpi.lgpio luma.oled pillow
  ```
- MOC (Music On Console) installé pour la lecture audio :
  ```
  sudo apt install moc
  ```
- Activez I2C sur le Raspberry Pi via `raspi-config` (Interface Options > I2C > Yes).

## Installation
1. Clonez le dépôt GitHub :
   ```
   git clone https://github.com/cstoyanov-cs/Reveil-Pi.git
   cd Reveil-Pi
   ```
2. Installez les dépendances comme indiqué ci-dessus.
3. Configurez MOC : Ajoutez vos fichiers musicaux dans un répertoire (ex. `/home/pi/Music`) et configurez MOC pour les jouer.
4. Lancez le script principal :
   ```
   python main.py
   ```
Pour un démarrage automatique au boot, creer un service.

## Utilisation
- **Démarrage :** L'écran affiche l'heure actuelle. Tournez l'encodeur pour entrer en mode menu.
- **Menus :**
  - Configurer Alarme 1/2 : Sélectionnez heure/minute, activez/désactivez.
  - Réglage de l'heure : Synchronisez avec le RTC si besoin.
  - Sortie : Retour à l'affichage principal.
- **Alarmes :** À l'heure programmée, MOC joue la musique. Appuyez sur l'encodeur pour arrêter. Si échec, buzzer sonne.
- **Interrupteurs :** Position ON active l'alarme ; OFF la désactive (override software).
- **Veille :** Écran s'éteint après 30 secondes d'inactivité ; rotation ou appui le réveille.


Explications globales : Les interruptions GPIO assurent une réactivité immédiate sans polling constant, économisant CPU. Le cache heure rafraîchit toutes les secondes via timer. Les alarmes sont stockées en registre RTC pour persistance.

## Contribution
Forkez le repo, modifiez, et soumettez une pull request. Signalez les bugs via issues.

## Licence
MIT License – Utilisez librement, mais citez la source.
```
