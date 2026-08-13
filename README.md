# CARATEC BMS BLE

Liest die 12-V-LiFePO4-Batterien im CARATEC/Niesmann+Bischoff-Wohnmobil über
Bluetooth Low Energy aus und stellt die Werte per MQTT in Home Assistant bereit.

## Funktionen

- Ladezustand (SOC), Spannung, Strom und Leistung
- Restkapazität, Nennkapazität und Ladezyklen
- Einzelne Zellspannungen und Temperatur
- Fehlercode des BMS
- MQTT Auto-Discovery inklusive Availability-Topic
- Bis zu 4 Batterien

## Konfiguration

- **mqtt_host**: MQTT-Broker (Standard: `core-mosquitto`)
- **mqtt_user / mqtt_pass**: MQTT-Zugangsdaten
- **poll_interval**: Abfrage-Intervall in Sekunden (1–15, Standard 5)
- **batteries**: Liste der Batterien mit Name und BLE-Adresse

## Unterstützte Hardware

**Wattstunde Nova Core** BMS über BLE-Modul mit MAC-Präfix `10:23:81` oder `60:6E:41`.
Getestet mit den 105-Ah-Batterien im Niesmann+Bischoff Arto 88.

Die Protokoll-Dekodierung folgt der Referenz-Implementierung
[`aiobmsble`](https://github.com/patman15/aiobmsble) (`bms/ws_nova_bms.py`, Apache-2.0).

Details siehe [DOCS.md](DOCS.md).
