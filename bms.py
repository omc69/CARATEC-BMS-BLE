import asyncio
import json
import os
import logging
import paho.mqtt.client as mqtt
from bleak import BleakClient, BleakScanner
from datetime import datetime

BMS_VERSION = "2.2.0"
logging.basicConfig(level=logging.WARNING)

# Add-on Optionen aus /data/options.json lesen
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

mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
if MQTT_USER:
    mqttc.username_pw_set(MQTT_USER, MQTT_PASS)
mqttc.connect(MQTT_HOST, MQTT_PORT, 60)
mqttc.loop_start()

device_cache = {}
scan_lock = asyncio.Lock()

def ts():
    return datetime.now().strftime('%H:%M:%S')

def parse(frame):
    try:
        data = frame[1:]
        cells = []
        pos = 24
        for i in range(4):
            mv = int(data[pos:pos+4], 16)
            cells.append(round(mv/1000, 3))
            pos += 4
        voltage = round(sum(cells), 3)
        soc = None
        if "42424242" in data:
            idx = data.index("42424242") + 8
            soc = round(int(data[idx:idx+4], 16)/100, 1)
        # Kapazität aus 019A28-Marker (Nennkapazität in mAh -> Ah)
        capacity = None
        if "019A28" in data:
            cidx = data.index("019A28")
            capacity = round(int(data[cidx:cidx+6], 16)/1000, 1)
        return {"soc": soc, "voltage": voltage, "cells": cells, "capacity": capacity}
    except Exception:
        return None

def publish(name, data):
    mqttc.publish(f"pace_bms/{name}", json.dumps(data))
    print(f"{ts()} [{name}] SOC={data['soc']}% V={data['voltage']}V Cap={data.get('capacity')}Ah Zellen={data['cells']}")
    # SOC + Spannung + Kapazität
    for key, unit, dclass in [("soc", "%", "battery"), ("voltage", "V", "voltage"), ("capacity", "Ah", None)]:
        disc = {
            "name": f"{name} {key}",
            "state_topic": f"pace_bms/{name}",
            "value_template": f"{{{{ value_json.{key} }}}}",
            "unique_id": f"pace_bms_{name}_{key}",
            "unit_of_measurement": unit,
            "device": {"identifiers": [name], "name": f"PACE BMS {name}"}
        }
        if dclass:
            disc["device_class"] = dclass
        mqttc.publish(f"homeassistant/sensor/pace_bms_{name}_{key}/config",
                      json.dumps(disc), retain=True)
    # Einzelne Zellspannungen
    for i, cv in enumerate(data["cells"], 1):
        disc = {
            "name": f"{name} cell_{i}",
            "state_topic": f"pace_bms/{name}",
            "value_template": f"{{{{ value_json.cells[{i-1}] }}}}",
            "unique_id": f"pace_bms_{name}_cell_{i}",
            "unit_of_measurement": "V",
            "device_class": "voltage",
            "device": {"identifiers": [name], "name": f"PACE BMS {name}"}
        }
        mqttc.publish(f"homeassistant/sensor/pace_bms_{name}_cell_{i}/config",
                      json.dumps(disc), retain=True)

async def shared_scan():
    async with scan_lock:
        devices = await BleakScanner.discover(timeout=10.0)
        for d in devices:
            device_cache[d.address.upper()] = d

async def monitor(name, addr):
    assembly = ""
    def handler(s, data):
        nonlocal assembly
        assembly += data.decode('ascii', errors='ignore')
        while ':' in assembly[1:]:
            nc = assembly.index(':', 1)
            frame = assembly[:nc]
            assembly = assembly[nc:]
            if frame.startswith(':') and len(frame) > 50:
                r = parse(frame)
                if r and r['soc'] is not None:
                    publish(name, r)

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
                await asyncio.sleep(15)
                continue
            print(f"{ts()} [{name}] Verbinde {addr}...")
            client = BleakClient(device, timeout=20.0)
            await client.connect()
            print(f"{ts()} [{name}] Verbunden!")
            await client.start_notify(NOTIFY, handler)
            while client.is_connected:
                await asyncio.sleep(POLL)
        except Exception as e:
            print(f"{ts()} [{name}] Fehler: {e}")
            device_cache.pop(addr.upper(), None)
        finally:
            if client:
                try:
                    await client.disconnect()
                except Exception:
                    pass
            await asyncio.sleep(10)

async def main():
    print(f"{ts()} PACE BMS BLE v{BMS_VERSION} | MQTT: {MQTT_HOST}:{MQTT_PORT} | Poll: {POLL}s")
    print(f"{ts()} {len(BATTERIES)} Batterien konfiguriert")
    if not BATTERIES:
        print(f"{ts()} WARNUNG: Keine Batterien konfiguriert!")
        return
    await shared_scan()
    tasks = []
    for name_addr in BATTERIES:
        name = name_addr["name"]
        addr = name_addr["address"]
        tasks.append(asyncio.create_task(monitor(name, addr)))
        await asyncio.sleep(8)
    await asyncio.gather(*tasks)

asyncio.run(main())