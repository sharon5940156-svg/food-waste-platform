import json
import math
import os
import random
import time
from datetime import datetime, timezone
import paho.mqtt.client as mqtt

HOST = os.getenv("MQTT_HOST", "mqtt")
PORT = int(os.getenv("MQTT_PORT", "1883"))
BASE = os.getenv("MQTT_TOPIC_BASE", "food/telemetry")
INTERVAL = int(os.getenv("INTERVAL_SECONDS", "10"))

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="food-waste-sensor-simulator")
while True:
    try:
        client.connect(HOST, PORT, 60)
        print("[SENSOR] MQTT connected", flush=True)
        break
    except Exception as exc:
        print(f"[SENSOR] MQTT unavailable: {exc}; retrying...", flush=True)
        time.sleep(3)

tick = 0
while True:
    tick += 1
    for batch_id, base_temp, base_humidity in [
        (1, 4.0, 70.0),
        (2, 3.0, 75.0),
        (3, 4.0, 68.0),
    ]:
        temperature = round(base_temp + 0.8 * math.sin(tick / 4 + batch_id) + random.uniform(-0.2, 0.2), 2)
        humidity = round(base_humidity + 3.0 * math.sin(tick / 5 + batch_id) + random.uniform(-1.0, 1.0), 2)
        payload = {
            "batch_id": batch_id,
            "temperature_c": temperature,
            "humidity": humidity,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        client.publish(f"{BASE}/{batch_id}", json.dumps(payload), qos=1)
        print(f"[SENSOR] batch={batch_id} temp={temperature}C humidity={humidity}%", flush=True)
    time.sleep(INTERVAL)
