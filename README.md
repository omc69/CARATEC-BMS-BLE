# CARATEC Add-ons für Home Assistant

Add-on-Repository für Wohnmobile der CARATEC- und Niesmann+Bischoff-Reihe.

## Installation

1. In Home Assistant: **Einstellungen → Add-ons → Add-on-Store**
2. Oben rechts das Dreipunktmenü → **Repositories**
3. Diese URL eintragen und hinzufügen:

   ```
   https://github.com/omc69/CARATEC-BMS-BLE
   ```

4. Der Store zeigt jetzt den Abschnitt **CARATEC Add-ons**. Add-on auswählen,
   installieren, konfigurieren, starten.

Beim ersten Start baut der Supervisor das Docker-Abbild auf dem Zielgerät.
Auf einem Raspberry Pi dauert das ein paar Minuten — das ist normal und passiert
nur einmal je Version.

## Enthaltene Add-ons

### [CARATEC BMS BLE](caratec_batteries/)

Liest Wattstunde-Nova-Core-Batterien über Bluetooth Low Energy aus und stellt
die Werte per MQTT-Discovery in Home Assistant bereit: Ladezustand, Spannung,
Strom, Leistung, Restkapazität, Zyklen, Zelltemperatur, einzelne Zellspannungen
und den Fehlercode des BMS.

Voraussetzungen: ein MQTT-Broker (etwa das Mosquitto-Add-on) und ein
BLE-fähiger Host. Getestet auf Raspberry Pi 5 mit Home Assistant OS.

## Voraussetzungen an den Host

Das Add-on braucht direkten Zugriff auf den Bluetooth-Adapter des Hosts
(`host_dbus`, `SYS_RAWIO`). Läuft parallel eine andere Integration auf demselben
Adapter — etwa `bms_ble` —, streiten sich beide um die Verbindung. Nur eine von
beiden betreiben.

## Lizenz

Siehe [LICENSE](LICENSE).
