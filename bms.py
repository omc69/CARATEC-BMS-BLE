"""CARATEC BMS BLE - Wattstunde Nova Core.

Protokoll nach aiobmsble/bms/ws_nova_bms.py (Apache-2.0):
Frame ':' <ascii-hex> <cksum2> '~', XOR-Key aus Zeichen 7..8,
Nutzdaten ab Byte 44, Zellspannungen ab Byte 12, Temperaturen ab Byte 48.
"""
import asyncio
import json
import logging
from string import hexdigits

import paho.mqtt.client as mqtt
from bleak import BleakClient, BleakScanner
from datetime import datetime

BMS_VERSION = "3.0.0-wsnova"
logging.basicConfig(level=logging.WARNING)

OPTIONS_FILE = "/data/options.json"
try:
    with open(OPTIONS_FILE) as f:
        OPTS = json.load(f)
except Exception:
    OPTS = {}

MQTT_HOST = OPTS.get("mqtt_host", "core-mosquitto")
MQTT_PORT = int(OPTS.get("mqtt_port", 1883))
MQTT_USER = OPTS.get("mqtt_user", "mqtt")
MQTT_PASS = OPTS.get("mqtt_pass", "")
POLL = int(OPTS.get("poll_interval", 5))
BATTERIES = OPTS.get("batteries", [])

NOTIFY = "0000fff1-0000-1000-8000-00805f9b34fb"
REQUEST = b":015150000EFE~"   # Datenanforderung (aiobmsble ws_nova)
HEAD, TAIL = ":", "~"
MIN_FRAME = 238
DATA_START = 44
CELL_START, CELL_COUNT = 12, 16
TEMP_START, TEMP_COUNT, TEMP_OFFSET = 48, 4, 40

mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
if MQTT_USER:
    mqttc.username_pw_set(MQTT_USER, MQTT_PASS)

device_cache = {}
scan_lock = asyncio.Lock()
discovered = set()


def ts():
    return datetime.now().strftime("%H:%M:%S")


def avail_topic(name):
    return f"pace_bms/{name}/availability"


def mqtt_connect():
    for b in BATTERIES:
        mqttc.will_set(avail_topic(b["name"]), "offline", retain=True)
    delay = 2
    while True:
        try:
            mqttc.connect(MQTT_HOST, MQTT_PORT, 60)
            mqttc.loop_start()
            print(f"{ts()} MQTT verbunden: {MQTT_HOST}:{MQTT_PORT}")
            return
        except Exception as e:
            print(f"{ts()} MQTT-Verbindung fehlgeschlagen ({e}), retry in {delay}s")
            import time
            time.sleep(delay)
            delay = min(delay * 2, 60)


def parse(frame):
    """Dekodiert ein Wattstunde-Nova-Frame. Gibt dict oder None zurueck."""
    try:
        if not frame.startswith(HEAD) or TAIL not in frame:
            return None
        body = frame[: frame.index(TAIL)]
        hx = "".join(c for c in body[1:] if c in hexdigits)
        if len(hx) < MIN_FRAME - 10:
            return None
        key = int(hx[6:8], 16)
        payload = hx[:-2]                      # Pruefsumme abschneiden
        if len(payload) % 2:
            payload = payload[:-1]
        d = bytes(b ^ key for b in bytes.fromhex(payload))
        if not d.startswith(b"\x01\x54"):
            return None
        if len(d) < DATA_START + 34:
            return None

        def u(off, n):
            return int.from_bytes(d[off:off + n], "big")

        cells = [u(CELL_START + 2 * i, 2) / 1000 for i in range(CELL_COUNT)]
        cells = [round(c, 3) for c in cells if c]

        S = DATA_START
        raw_cur = u(S + 10, 4)
        current = round((raw_cur & 0x7FFF) / 1000 * (-1 if raw_cur >> 15 else 1), 3)
        temps = [u(TEMP_START + i, 1) - TEMP_OFFSET for i in range(TEMP_COUNT)]

        return {
            "soc": u(S + 25, 1),
            "voltage": round(u(S + 18, 2) / 1000, 3),
            "current": current,
            "power": round(u(S + 18, 2) / 1000 * current, 1),
            "cycles": u(S + 23, 2),
            "capacity": u(S + 26, 4) // 1000,
            "remaining": round(u(S + 30, 4) / 1000, 3),
            "cells": cells,
            "temperature": max(temps),
            "temps": temps,
            "problem": u(S, 2) & 0x0FFC,
        }
    except Exception:
        return None


SENSORS = [
    ("soc", "SOC", "%", "battery", "measurement"),
    ("voltage", "Spannung", "V", "voltage", "measurement"),
    ("current", "Strom", "A", "current", "measurement"),
    ("power", "Leistung", "W", "power", "measurement"),
    ("remaining", "Restkapazitaet", "Ah", None, "measurement"),
    ("capacity", "Nennkapazitaet", "Ah", None, None),
    ("cycles", "Zyklen", None, None, "measurement"),
    ("temperature", "Temperatur", "°C", "temperature", "measurement"),
    ("problem", "Fehlercode", None, None, None),
]


def device_block(name):
    return {
        "identifiers": [name],
        "name": f"PACE BMS {name}",
        "manufacturer": "Wattstunde",
        "model": "Nova Core",
        "sw_version": BMS_VERSION,
    }


def publish_discovery(name, cells):
    for key, label, unit, dclass, sclass in SENSORS:
        disc = {
            "name": f"{name} {key}",
            "state_topic": f"pace_bms/{name}",
            "availability_topic": avail_topic(name),
            "value_template": f"{{{{ value_json.{key} }}}}",
            "unique_id": f"pace_bms_{name}_{key}",
            "device": device_block(name),
        }
        if unit:
            disc["unit_of_measurement"] = unit
        if dclass:
            disc["device_class"] = dclass
        if sclass:
            disc["state_class"] = sclass
        mqttc.publish(f"homeassistant/sensor/pace_bms_{name}_{key}/config",
                      json.dumps(disc), retain=True)
    for i in range(1, len(cells) + 1):
        disc = {
            "name": f"{name} cell_{i}",
            "state_topic": f"pace_bms/{name}",
            "availability_topic": avail_topic(name),
            "value_template": f"{{{{ value_json.cells[{i - 1}] }}}}",
            "unique_id": f"pace_bms_{name}_cell_{i}",
            "unit_of_measurement": "V",
            "device_class": "voltage",
            "state_class": "measurement",
            "device": device_block(name),
        }
        mqttc.publish(f"homeassistant/sensor/pace_bms_{name}_cell_{i}/config",
                      json.dumps(disc), retain=True)
    print(f"{ts()} [{name}] Discovery gesendet ({len(SENSORS)} Sensoren + {len(cells)} Zellen)")


def publish(name, data):
    if name not in discovered:
        publish_discovery(name, data["cells"])
        discovered.add(name)
    mqttc.publish(avail_topic(name), "online", retain=True)
    mqttc.publish(f"pace_bms/{name}", json.dumps(data), retain=True)
    print(f"{ts()} [{name}] SOC={data['soc']}% V={data['voltage']}V I={data['current']}A "
          f"Rest={data['remaining']}/{data['capacity']}Ah Zyk={data['cycles']} "
          f"T={data['temperature']}C Zellen={data['cells']}")


async def shared_scan():
    async with scan_lock:
        for d in await BleakScanner.discover(timeout=10.0):
            device_cache[d.address.upper()] = d


async def monitor(name, addr):
    assembly = ""
    last = [0.0]

    def handler(_s, data):
        nonlocal assembly
        assembly += data.decode("ascii", errors="ignore")
        while TAIL in assembly:
            t = assembly.index(TAIL)
            chunk, assembly = assembly[: t + 1], assembly[t + 1:]
            st = chunk.rfind(HEAD)
            if st < 0:
                continue
            r = parse(chunk[st:])
            if r:
                now = asyncio.get_event_loop().time()
                if now - last[0] >= POLL:
                    last[0] = now
                    publish(name, r)
        if len(assembly) > 4096:
            assembly = assembly[-1024:]

    while True:
        client = None
        try:
            device = device_cache.get(addr.upper())
            if not device:
                print(f"{ts()} [{name}] Scanning...")
                await shared_scan()
                device = device_cache.get(addr.upper())
            if not device:
                print(f"{ts()} [{name}] Nicht gefunden, retry...")
                mqttc.publish(avail_topic(name), "offline", retain=True)
                await asyncio.sleep(15)
                continue
            print(f"{ts()} [{name}] Verbinde {addr}...")
            client = BleakClient(device, timeout=20.0)
            await client.connect()
            print(f"{ts()} [{name}] Verbunden!")
            await client.start_notify(NOTIFY, handler)
            while client.is_connected:
                try:
                    await client.write_gatt_char(NOTIFY, REQUEST, response=False)
                except Exception as e:
                    print(f"{ts()} [{name}] Request-Fehler: {e}")
                await asyncio.sleep(POLL)
        except Exception as e:
            print(f"{ts()} [{name}] Fehler: {e}")
            device_cache.pop(addr.upper(), None)
        finally:
            mqttc.publish(avail_topic(name), "offline", retain=True)
            if client:
                try:
                    await client.disconnect()
                except Exception:
                    pass
            await asyncio.sleep(10)


async def main():
    print(f"{ts()} CARATEC BMS BLE v{BMS_VERSION} (Wattstunde Nova Core) | "
          f"MQTT: {MQTT_HOST}:{MQTT_PORT} | Poll: {POLL}s")
    print(f"{ts()} {len(BATTERIES)} Batterien konfiguriert")
    if not BATTERIES:
        print(f"{ts()} WARNUNG: Keine Batterien konfiguriert!")
        return
    await shared_scan()
    tasks = []
    for b in BATTERIES:
        tasks.append(asyncio.create_task(monitor(b["name"], b["address"])))
        await asyncio.sleep(8)
    await asyncio.gather(*tasks)


mqtt_connect()
asyncio.run(main())
