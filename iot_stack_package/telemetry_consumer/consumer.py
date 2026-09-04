import json
import os
import time
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from kafka import KafkaConsumer

BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:19092")
TOPIC = os.getenv("KAFKA_TOPIC", "telemetry.raw")
GROUP = os.getenv("KAFKA_GROUP", "telemetry-backend")
BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000").rstrip("/")

def post_telemetry(payload):
    body = {
        "batch_id": int(payload["batch_id"]),
        "temperature_c": float(payload["temperature_c"]),
        "humidity": float(payload["humidity"]),
    }
    req = Request(
        f"{BACKEND_URL}/telemetry",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=10) as response:
        return response.status

while True:
    try:
        print("[CONSUMER] Connecting to Kafka...", flush=True)
        consumer = KafkaConsumer(
            TOPIC,
            bootstrap_servers=BOOTSTRAP,
            group_id=GROUP,
            auto_offset_reset="latest",
            enable_auto_commit=True,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        )
        print("[CONSUMER] Kafka connected", flush=True)
        for message in consumer:
            try:
                status = post_telemetry(message.value)
                print(f"[CONSUMER] Kafka -> FastAPI status={status} batch={message.value.get('batch_id')}", flush=True)
            except (HTTPError, URLError, ValueError, KeyError) as exc:
                print(f"[CONSUMER] Backend error: {exc}", flush=True)
    except Exception as exc:
        print(f"[CONSUMER] Kafka unavailable: {exc}; retrying...", flush=True)
        time.sleep(3)
