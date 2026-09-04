import json
import os
import time
from kafka import KafkaProducer
import paho.mqtt.client as mqtt

MQTT_HOST = os.getenv("MQTT_HOST", "mqtt")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "food/telemetry/#")
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:19092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "telemetry.raw")

def connect_kafka():
    while True:
        try:
            producer = KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                retries=10,
            )
            print("[EDGE] Kafka connected", flush=True)
            return producer
        except Exception as exc:
            print(f"[EDGE] Kafka unavailable: {exc}; retrying...", flush=True)
            time.sleep(3)

producer = connect_kafka()

def on_connect(client, userdata, flags, reason_code, properties=None):
    print(f"[EDGE] MQTT connected: {reason_code}", flush=True)
    client.subscribe(MQTT_TOPIC, qos=1)
    print(f"[EDGE] Subscribed: {MQTT_TOPIC}", flush=True)

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        required = ("batch_id", "temperature_c", "humidity")
        if any(k not in payload for k in required):
            print(f"[EDGE] Ignored invalid payload: {payload}", flush=True)
            return
        payload["source"] = "mqtt-edge-gateway"
        producer.send(KAFKA_TOPIC, value=payload)
        producer.flush()
        print(f"[EDGE] MQTT -> Kafka batch={payload['batch_id']}", flush=True)
    except Exception as exc:
        print(f"[EDGE] Message error: {exc}", flush=True)

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="food-waste-edge-gateway")
client.on_connect = on_connect
client.on_message = on_message

while True:
    try:
        print("[EDGE] Connecting to MQTT...", flush=True)
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        client.loop_forever()
    except Exception as exc:
        print(f"[EDGE] MQTT unavailable: {exc}; retrying...", flush=True)
        time.sleep(3)
