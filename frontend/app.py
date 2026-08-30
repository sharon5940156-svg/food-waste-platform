import os

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from requests.exceptions import RequestException

BACKEND_CANDIDATES = [
    os.getenv("BACKEND_URL", "").rstrip("/"),
    "http://backend:8000",
    "http://localhost:8000",
]
BACKEND_CANDIDATES = [url for url in BACKEND_CANDIDATES if url]

STATUS_COLORS = {
    "in_storage": ("#d1fae5", "#065f46"),
    "in_transit": ("#dbeafe", "#1e40af"),
    "at_risk": ("#ffedd5", "#9a3412"),
    "expired": ("#fee2e2", "#991b1b"),
}


def resolve_backend() -> str:
    for base in BACKEND_CANDIDATES:
        try:
            response = requests.get(f"{base}/health", timeout=2)
            if response.ok:
                return base
        except RequestException:
            continue
    return BACKEND_CANDIDATES[0]


def api_get(path: str, timeout: float = 5):
    response = requests.get(f"{st.session_state.api_base}{path}", timeout=timeout)
    response.raise_for_status()
    return response.json()


def api_post(path: str, payload: dict, timeout: float = 5):
    response = requests.post(
        f"{st.session_state.api_base}{path}",
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def check_health() -> bool:
    try:
        data = api_get("/health", timeout=2)
        return data.get("status") == "ok"
    except RequestException:
        return False


def status_badge(status: str) -> str:
    bg, fg = STATUS_COLORS.get(status, ("#e2e8f0", "#334155"))
    label = status.replace("_", " ").title()
    return (
        f'<span style="background:{bg};color:{fg};padding:4px 10px;border-radius:999px;'
        f'font-size:0.78rem;font-weight:600;letter-spacing:0.02em;">{label}</span>'
    )


def risk_level(score: float) -> tuple[str, str]:
    if score < 0.3:
        return "Low", "#059669"
    if score < 0.6:
        return "Elevated", "#d97706"
    return "High", "#dc2626"


st.set_page_config(
    page_title="Perishable Inventory & Forecast",
    page_icon="🥬",
    layout="wide",
)

st.markdown(
    """
    <style>
      .block-container { padding-top: 1.4rem; }
      .hero-title { font-size: 1.85rem; font-weight: 700; margin-bottom: 0.15rem; }
      .hero-sub { color: #64748b; margin-bottom: 0.6rem; }
      .health-ok { color: #047857; font-weight: 700; }
      .health-down { color: #b91c1c; font-weight: 700; }
      div[data-testid="stMetricValue"] { font-size: 1.45rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

if "api_base" not in st.session_state:
    st.session_state.api_base = resolve_backend()

healthy = check_health()
if not healthy:
    st.session_state.api_base = resolve_backend()
    healthy = check_health()

header_left, header_right = st.columns([4, 1.4])
with header_left:
    st.markdown(
        '<div class="hero-title">Perishable Food Inventory &amp; Demand Forecasting</div>'
        '<div class="hero-sub">Monitor batches, ingest cold-chain telemetry, and forecast remaining shelf life.</div>',
        unsafe_allow_html=True,
    )
with header_right:
    if healthy:
        st.markdown(
            f'<p class="health-ok">● System healthy</p><p style="color:#64748b;font-size:0.8rem;">{st.session_state.api_base}</p>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<p class="health-down">● API unreachable</p><p style="color:#64748b;font-size:0.8rem;">{st.session_state.api_base}</p>',
            unsafe_allow_html=True,
        )

if not healthy:
    st.error("Cannot reach the FastAPI backend. Confirm the `backend` container is running.")
    st.stop()

try:
    products = api_get("/products")
    batches = api_get("/batches")
except RequestException as exc:
    st.error(f"Failed to load inventory: {exc}")
    st.stop()

product_by_id = {item["id"]: item for item in products}
batch_labels = {
    f"Batch {b['id']} · {product_by_id.get(b['product_id'], {}).get('name', 'Unknown')}": b["id"]
    for b in batches
}

tab_inventory, tab_telemetry, tab_forecast = st.tabs(
    ["Inventory & Batches", "Telemetry Ingestion", "AI Forecast & Risk Analytics"]
)

with tab_inventory:
    st.subheader("Registered products")
    product_df = pd.DataFrame(products)
    if product_df.empty:
        st.info("No products registered yet.")
    else:
        st.dataframe(
            product_df.rename(
                columns={
                    "id": "ID",
                    "name": "Product",
                    "base_shelf_life_days": "Base shelf life (days)",
                    "optimal_temp_c": "Optimal temp (°C)",
                }
            ),
            hide_index=True,
            use_container_width=True,
        )

    st.subheader("Active batches")
    if not batches:
        st.info("No batches available.")
    else:
        cards = st.columns(min(3, len(batches)))
        for index, batch in enumerate(batches):
            product = product_by_id.get(batch["product_id"], {})
            with cards[index % 3]:
                st.markdown(
                    f"""
                    <div style="border:1px solid #e2e8f0;border-radius:14px;padding:16px 16px 8px;margin-bottom:12px;">
                      <div style="display:flex;justify-content:space-between;align-items:center;">
                        <strong>Batch #{batch['id']}</strong>
                        {status_badge(batch['current_status'])}
                      </div>
                      <p style="margin:8px 0 4px;font-size:1.05rem;">{product.get('name', 'Unknown product')}</p>
                      <p style="color:#64748b;margin:0;">{batch['quantity_kg']} kg</p>
                      <p style="color:#64748b;font-size:0.85rem;margin:8px 0 0;">
                        Produced {batch['production_date']} · Expires {batch['expiry_date']}
                      </p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        batch_df = pd.DataFrame(batches)
        batch_df["product"] = batch_df["product_id"].map(
            lambda pid: product_by_id.get(pid, {}).get("name", "Unknown")
        )
        st.dataframe(
            batch_df[
                [
                    "id",
                    "product",
                    "quantity_kg",
                    "production_date",
                    "expiry_date",
                    "current_status",
                ]
            ].rename(
                columns={
                    "id": "Batch ID",
                    "product": "Product",
                    "quantity_kg": "Quantity (kg)",
                    "production_date": "Production date",
                    "expiry_date": "Expiry date",
                    "current_status": "Status",
                }
            ),
            hide_index=True,
            use_container_width=True,
        )

with tab_telemetry:
    st.subheader("Simulate a sensor reading")
    st.caption("Log temperature and humidity for a batch. Spoilage risk is calculated on ingest.")

    if not batches:
        st.warning("Create a batch before ingesting telemetry.")
    else:
        with st.form("telemetry_form", clear_on_submit=False):
            selected_label = st.selectbox("Batch", options=list(batch_labels.keys()))
            col_temp, col_hum = st.columns(2)
            with col_temp:
                temperature = st.slider("Temperature (°C)", min_value=-5.0, max_value=25.0, value=4.0, step=0.1)
            with col_hum:
                humidity = st.slider("Humidity (%)", min_value=0.0, max_value=100.0, value=70.0, step=0.5)
            submitted = st.form_submit_button("Log telemetry", type="primary")

        if submitted:
            batch_id = batch_labels[selected_label]
            try:
                reading = api_post(
                    "/telemetry",
                    {
                        "batch_id": batch_id,
                        "temperature_c": temperature,
                        "humidity": humidity,
                    },
                )
                st.success(
                    f"Recorded {reading['temperature_c']}°C / {reading['humidity']}% for batch {batch_id}."
                )
                st.metric("Instant spoilage risk", f"{reading['spoilage_risk_score']:.1%}")
            except RequestException as exc:
                detail = getattr(exc.response, "text", str(exc)) if getattr(exc, "response", None) else str(exc)
                st.error(f"Ingest failed: {detail}")

with tab_forecast:
    st.subheader("Dynamic shelf-life forecast")
    if not batches:
        st.warning("No batches available to forecast.")
    else:
        selected_label = st.selectbox(
            "Select batch",
            options=list(batch_labels.keys()),
            key="forecast_batch",
        )
        batch_id = batch_labels[selected_label]
        product = product_by_id.get(
            next(b["product_id"] for b in batches if b["id"] == batch_id),
            {},
        )
        optimal_temp = product.get("optimal_temp_c", 4.0)

        try:
            forecast = api_get(f"/batches/{batch_id}/forecast")
            readings = api_get(f"/batches/{batch_id}/telemetry")
        except RequestException as exc:
            st.error(f"Failed to load forecast data: {exc}")
        else:
            level, color = risk_level(forecast["spoilage_risk_score"])
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Remaining shelf life", f"{forecast['remaining_shelf_life_days']:.2f} days")
            m2.metric("Spoilage risk", f"{forecast['spoilage_risk_score']:.1%}")
            m3.metric("Predicted temperature", f"{forecast['predicted_temperature_c']:.1f} °C")
            m4.metric("Model", forecast["forecast_method"].replace("_", " ").title())
            st.markdown(
                f'<p style="color:{color};font-weight:600;">Risk level: {level} · {forecast["sample_count"]} telemetry samples</p>',
                unsafe_allow_html=True,
            )

            if not readings:
                st.info("No telemetry yet for this batch. Log readings in the Telemetry Ingestion tab.")
            else:
                frame = pd.DataFrame(readings)
                frame["time"] = pd.to_datetime(frame["time"])
                figure = go.Figure()
                figure.add_trace(
                    go.Scatter(
                        x=frame["time"],
                        y=frame["temperature_c"],
                        mode="lines+markers",
                        name="Temperature (°C)",
                        line={"color": "#0f766e", "width": 2},
                    )
                )
                figure.add_trace(
                    go.Scatter(
                        x=frame["time"],
                        y=frame["humidity"],
                        mode="lines+markers",
                        name="Humidity (%)",
                        yaxis="y2",
                        line={"color": "#2563eb", "width": 2, "dash": "dot"},
                    )
                )
                figure.add_hline(
                    y=optimal_temp,
                    line_dash="dash",
                    line_color="#dc2626",
                    annotation_text=f"Optimal {optimal_temp}°C",
                    annotation_position="top left",
                )
                figure.update_layout(
                    margin={"l": 10, "r": 10, "t": 30, "b": 10},
                    hovermode="x unified",
                    legend={"orientation": "h", "y": 1.12},
                    yaxis={"title": "Temperature (°C)"},
                    yaxis2={
                        "title": "Humidity (%)",
                        "overlaying": "y",
                        "side": "right",
                        "range": [0, 100],
                    },
                    xaxis={"title": "Time"},
                )
                st.plotly_chart(figure, use_container_width=True)

                if frame["spoilage_risk_score"].notna().any():
                    risk_fig = go.Figure(
                        go.Scatter(
                            x=frame["time"],
                            y=frame["spoilage_risk_score"],
                            mode="lines+markers",
                            name="Spoilage risk",
                            line={"color": "#c2410c"},
                            fill="tozeroy",
                        )
                    )
                    risk_fig.update_layout(
                        title="Calculated spoilage risk over time",
                        yaxis={"title": "Risk score", "range": [0, 1]},
                        xaxis={"title": "Time"},
                        margin={"l": 10, "r": 10, "t": 50, "b": 10},
                    )
                    st.plotly_chart(risk_fig, use_container_width=True)
