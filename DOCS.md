# CARATEC BMS BLE

Liest LiFePO4-Batterien mit PACE BMS (V20-Protokoll) über Bluetooth Low Energy aus und stellt die Werte per MQTT in Home Assistant bereit.

## Funktionsweise

Die Batterien nutzen ein Barrot BR2262e BLE-Modul, das den UART-Datenstrom des PACE BMS transparent durchleitet. Das Add-on verbindet sich per BLE, abonniert die Notify-Characteristic `FFF1`, setzt die fragmentierten ASCII-Frames (`:`-Präfix) zusammen und dekodiert daraus Ladezustand, Spannung und Zellspannungen. Die Werte werden per MQTT mit Auto-Discovery an Home Assistant gemeldet.

## Voraussetzungen

- **Mosquitto Broker** Add-on installiert und gestartet
- **MQTT Integration** in Home Assistant eingerichtet
- Ein MQTT-Benutzer (anlegen unter Einstellungen → Personen → Benutzer)
- Bluetooth-Adapter am Host (Raspberry Pi intern oder USB-Dongle)

## Installation

1. Add-on installieren und starten
2. Unter Konfiguration MQTT-Zugangsdaten und Batterien eintragen
3. Add-on neu starten
4. Sensoren erscheinen automatisch unter Einstellungen → Geräte & Dienste → MQTT

## Konfiguration

### mqtt_host
Adresse des MQTT-Brokers. Bei Nutzung des Mosquitto-Add-ons: `core-mosquitto`.

### mqtt_port
Port des Brokers. Standard: `1883`.

### mqtt_user / mqtt_pass
Zugangsdaten eines Home-Assistant-Benutzers für MQTT. Der Benutzer darf nicht `homeassistant` oder `addons` heißen (reservierte Namen).

### poll_interval
Abfrage-Intervall in Sekunden (1-60). Die Batterie pusht ihre Daten von selbst etwa alle 3 Sekunden; dieser Wert steuert das interne Verbindungs-Polling.

### batteries
Liste der Batterien. Pro Eintrag:
- **name**: Eindeutiger Name (z.B. `battery_1`). Wird im MQTT-Topic und Sensornamen verwendet.
- **address**: BLE-MAC-Adresse der Batterie (Format `10:23:81:8B:13:AD`).

Bis zu 4 Batterien werden unterstützt.

### Beispiel-Konfiguration

```yaml
mqtt_host: core-mosquitto
mqtt_port: 1883
mqtt_user: mqtt
mqtt_pass: geheim
poll_interval: 5
batteries:
  - name: battery_1
    address: "10:23:81:8B:13:1A"
  - name: battery_2
    address: "10:23:81:8B:13:AD"
```

## Bereitgestellte Sensoren

Pro Batterie werden folgende Sensoren erzeugt:

| Sensor | Einheit | Beschreibung |
|--------|---------|--------------|
| `{name}_soc` | % | Ladezustand (State of Charge) |
| `{name}_voltage` | V | Gesamtspannung (Summe der Zellen) |
| `{name}_cell_1` … `cell_4` | V | Einzelne Zellspannungen |

## MQTT-Topics

- Daten: `pace_bms/{name}` (JSON mit `soc`, `voltage`, `cells`)
- Discovery: `homeassistant/sensor/pace_bms_{name}_{key}/config`

## BLE-Adresse herausfinden

Falls du die MAC-Adresse einer Batterie nicht kennst, im Terminal:

```bash
bluetoothctl
scan on
```

Batterien erscheinen meist als `BT-Battery`. Adresse notieren, dann `scan off` und `quit`.

## Mehrere Batterien an einem Adapter

Der interne Bluetooth-Adapter eines Raspberry Pi kann nur eine begrenzte Zahl gleichzeitiger BLE-Verbindungen halten. Das Add-on nutzt einen gemeinsamen Scanner mit Sperre und zeitlichem Versatz, um Kollisionen (`org.bluez.Error.InProgress`) zu vermeiden. Bei vielen Geräten (mehrere Batterien plus weitere BLE-Sensoren) empfiehlt sich ein dedizierter USB-Bluetooth-Dongle oder ein ESPHome-Bluetooth-Proxy.

## Fehlerbehebung

**Batterie wird nicht gefunden**
Adapter belegt oder Gerät außer Reichweite. Prüfen mit `bluetoothctl scan on`. Ggf. Adapter zurücksetzen: `bluetoothctl power off` / `power on`.

**Connection Refused: not authorised (MQTT)**
MQTT-Benutzer/Passwort falsch oder nicht angelegt. Benutzer unter Einstellungen → Personen → Benutzer erstellen.

**org.bluez.Error.InProgress**
Zwei Scans gleichzeitig. Tritt beim Start kurz auf, löst sich durch den eingebauten Versatz. Bei Dauerproblemen Poll-Intervall erhöhen oder BT-Proxy nutzen.

**Verbindung hängt nach Absturz**
Das Add-on trennt Verbindungen sauber im `finally`-Block. Bei hängendem Adapter hilft ein Neustart des Add-ons oder `bluetoothctl power off/on`.

## Bluetooth-Adapter zurücksetzen

Bei hängenden Verbindungen, `org.bluez.Error.InProgress` oder wenn Batterien nicht mehr gefunden werden, hilft ein Reset des Bluetooth-Adapters. Im Terminal ausführen:

```bash
bluetoothctl -- power off
sleep 2
bluetoothctl -- power on
```

Danach das Add-on neu starten. Der Adapter ist dann freigeräumt und alte Verbindungen sind gekappt.

Falls noch Prozesse den Adapter blockieren (z.B. ein altes Test-Script im Terminal), zusätzlich:

```bash
pkill -f python3
```

Achtung: Das beendet alle laufenden Python-Prozesse im Terminal – nicht das Add-on selbst, das läuft im eigenen Container.

## Unterstützte Hardware

- **BMS**: PACE BMS V20 (ASCII-Protokoll)
- **BLE-Modul**: Barrot BR2262e / BR2266e / BR2220e
- **Getestet mit**: NDS/Dometic LiFePO4-Batterien im Niesmann+Bischoff Arto 88

## Hinweise

Dieses Add-on wurde durch Reverse-Engineering des PACE-BLE-Protokolls erstellt und kommt ohne Gewähr. Die Dekodierung basiert auf beobachteten Frames; bei abweichenden BMS-Firmwares können Anpassungen am Parser nötig sein.