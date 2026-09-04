# MQTT + Edge Gateway + Kafka stack

Adds the event-streaming layer to the existing food-waste project.

Flow:
Sensor Simulator -> MQTT/Mosquitto -> Edge Gateway -> Kafka -> Telemetry Consumer -> FastAPI -> TimescaleDB -> React

The simulator is for local development/testing. In a real deployment it is replaced by physical/edge sensor publishers.
