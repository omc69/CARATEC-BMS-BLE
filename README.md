# CARATEC BMS BLE

Liest PACE BMS Batterien über Bluetooth (BLE) aus und published die Daten per MQTT an Home Assistant.

## Funktionen

- SOC (Ladezustand)
- Gesamtspannung
- Einzelne Zellspannungen
- Bis zu 4 Batterien
- Einstellbares Poll-Intervall

## Konfiguration

- **mqtt_host**: MQTT Broker (Standard: core-mosquitto)
- **mqtt_user / mqtt_pass**: MQTT Zugangsdaten
- **poll_interval**: Abfrage-Intervall in Sekunden (1-60)
- **batteries**: Liste der Batterien mit Name und BLE-Adresse

## Unterstützte Hardware

PACE BMS V20 Protokoll über Barrot BR2262e BLE-Modul.
Getestet mit NDS/Dometic LiFePO4 Batterien im Niesmann+Bischoff Arto 88.