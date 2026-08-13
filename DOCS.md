# CARATEC BMS BLE

Liest die 12-V-LiFePO4-Batterien im Wohnmobil über Bluetooth Low Energy aus und
stellt die Werte per MQTT in Home Assistant bereit.

## Funktionsweise

Die Batterien verwenden ein **Wattstunde Nova Core** BMS. Das Add-on verbindet sich
per BLE, abonniert die Notify-Characteristic `FFF1` und **schreibt zyklisch eine
Datenanforderung** (`:015150000EFE~`) auf dieselbe Characteristic. Das BMS antwortet
mit einem ASCII-Hex-Frame.

Frame-Aufbau:

```
: <ascii-hex-nutzdaten> <pruefsumme:2> ~
```

- Der XOR-Schlüssel steht in den Zeichen 7–8 des Frames und wird auf alle
  dekodierten Bytes angewendet (in der Praxis meist `0x00`).
- Gültige Frames beginnen nach der Dekodierung mit `0x01 0x54`.
- **Zellspannungen**: ab Byte 12, 16 Slots à 2 Byte in mV (unbenutzte Slots sind 0)
- **Datenblock**: ab Byte 44

| Feld | Offset ab Byte 44 | Länge | Umrechnung |
|------|-------------------|-------|------------|
| Fehlercode | 0 | 2 | `& 0x0FFC` |
| Strom | 10 | 4 | `(x & 0x7FFF)/1000`, negativ wenn Bit 15 gesetzt |
| Spannung | 18 | 2 | `/1000` |
| Zyklen | 23 | 2 | direkt |
| SOC | 25 | 1 | direkt in % |
| Nennkapazität | 26 | 4 | `//1000` → Ah |
| Restkapazität | 30 | 4 | `/1000` → Ah |
| Temperaturen | 48 (4 × 1 Byte) | 1 | Wert − 40 → °C |

Die Dekodierung folgt der Referenz-Implementierung
[`aiobmsble`](https://github.com/patman15/aiobmsble), Datei `bms/ws_nova_bms.py`
(Apache-2.0).

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
Zugangsdaten eines Home-Assistant-Benutzers für MQTT. Der Benutzer darf nicht
`homeassistant` oder `addons` heißen (reservierte Namen).

### poll_interval
Abfrage-Intervall in Sekunden, **1–15, Standard 5**.

Der Wert steuert zweierlei: wie oft die Datenanforderung geschrieben wird und wie
oft nach MQTT publiziert wird. Die Anfrage ist zugleich der Keepalive — **das BMS
trennt die Verbindung nach rund 20 Sekunden ohne Anfrage**. Werte über 15 führen
deshalb zu einer Endlosschleife aus Verbinden, Timeout und Neuverbinden, ohne dass
je Daten ankommen. Aus diesem Grund ist die Obergrenze im Schema auf 15 gesetzt.

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

Pro Batterie:

| Sensor | Einheit | Beschreibung |
|--------|---------|--------------|
| `{name}_soc` | % | Ladezustand, direkt vom BMS |
| `{name}_voltage` | V | Gesamtspannung des Packs |
| `{name}_current` | A | Strom, negativ beim Entladen |
| `{name}_power` | W | Leistung (Spannung × Strom) |
| `{name}_remaining` | Ah | Restkapazität |
| `{name}_capacity` | Ah | Nennkapazität |
| `{name}_cycles` | – | Ladezyklen |
| `{name}_temperature` | °C | höchster der vier Fühler |
| `{name}_problem` | – | Fehlercode, 0 = kein Fehler |
| `{name}_cell_1` … `cell_n` | V | Einzelne Zellspannungen |

Der SOC des BMS bezieht sich auf die tatsächliche, gealterte Kapazität und stimmt
deshalb nicht exakt mit `remaining / capacity` überein.

## MQTT-Topics

- Daten: `pace_bms/{name}` — JSON, retained
- Verfügbarkeit: `pace_bms/{name}/availability` — `online` / `offline`, retained,
  wird auch als Last Will gesetzt
- Discovery: `homeassistant/sensor/pace_bms_{name}_{key}/config` — retained,
  wird einmalig beim ersten gültigen Frame gesendet

Dank Availability-Topic melden die Sensoren sich sauber als *nicht verfügbar*,
sobald die BLE-Verbindung abreißt, statt einen veralteten Wert stehen zu lassen.

## BLE-Adresse herausfinden

```bash
bluetoothctl
scan on
```

Die Batterien erscheinen als `BT-CARATECONE` o.ä. Adresse notieren, dann `scan off`
und `quit`.

## Mehrere Batterien an einem Adapter

Der interne Bluetooth-Adapter eines Raspberry Pi kann nur eine begrenzte Zahl
gleichzeitiger BLE-Verbindungen halten. Das Add-on nutzt einen gemeinsamen Scanner
mit Sperre und zeitlichem Versatz, um Kollisionen (`org.bluez.Error.InProgress`) zu
vermeiden. Bei vielen Geräten empfiehlt sich ein dedizierter USB-Dongle oder ein
ESPHome-Bluetooth-Proxy.

## Fehlerbehebung

### Batterie wird nach einem Add-on-Neustart nicht mehr gefunden

Das ist der häufigste Fall und **kein Defekt**. Wird der Container hart beendet,
bleibt die BLE-Verbindung in BlueZ auf dem Host offen. Ein verbundenes BLE-Gerät
sendet keine Advertisements mehr, folglich findet der Scan es nicht.

Prüfen:

```bash
bluetoothctl info 10:23:81:8B:13:1A
```

Steht dort `Connected: yes`, obwohl das Add-on nicht läuft, ist es genau dieser Fall.
Lösung:

```bash
bluetoothctl disconnect 10:23:81:8B:13:1A
```

Die Batterie sendet danach binnen etwa 20 Sekunden wieder und wird gefunden.

### Verbindung bricht alle ~20 Sekunden ab, es kommen keine Daten

Die Datenanforderung erreicht das BMS nicht oder `poll_interval` ist zu hoch.
Wert auf 5 setzen. Bleibt es dabei, hilft ein Aus- und Einschalten der Batterien —
das BLE-Modul kann sich nach vielen abgebrochenen Verbindungen festfahren.

### Konflikt mit anderen BLE-Integrationen

Eine Batterie kann nur **eine** aktive BLE-Verbindung halten. Läuft parallel eine
Integration wie `bms_ble` auf dieselbe Adresse, werfen sich beide gegenseitig
heraus und keine bekommt Daten. In dem Fall eine der beiden entfernen.

### Connection Refused: not authorised (MQTT)

MQTT-Benutzer/Passwort falsch oder nicht angelegt. Benutzer unter
Einstellungen → Personen → Benutzer erstellen.

### org.bluez.Error.InProgress

Zwei Scans gleichzeitig. Tritt beim Start kurz auf und löst sich durch den
eingebauten Versatz.

## Bluetooth-Adapter zurücksetzen

Wenn ein gezieltes `disconnect` nicht reicht:

```bash
bluetoothctl -- power off
sleep 2
bluetoothctl -- power on
```

Danach das Add-on neu starten.

## Unterstützte Hardware

- **BMS**: Wattstunde Nova Core
- **BLE-Modul**: MAC-Präfix `10:23:81` oder `60:6E:41`, Service `FFF0`, Characteristic `FFF1`
- **Getestet mit**: 105-Ah-LiFePO4-Batterien im Niesmann+Bischoff Arto 88

## Hinweise

Die Dekodierung folgt der Referenz-Implementierung `aiobmsble` und wurde gegen echte
Frames verifiziert (Summe der Zellspannungen deckt sich exakt mit dem Spannungsfeld
des Frames). Bei abweichenden BMS-Firmwares können Anpassungen nötig sein.
