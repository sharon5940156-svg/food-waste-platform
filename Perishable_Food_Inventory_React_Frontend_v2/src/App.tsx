import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  Activity, AlertTriangle, Boxes, ChevronDown, Factory, LayoutDashboard,
  Menu, Package, RefreshCw, Settings, ShieldAlert, Thermometer, X, Droplets,
  Gauge, ArrowUpRight, Clock3
} from "lucide-react";
import {
  Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid,
  BarChart, Bar, Legend, ReferenceLine
} from "recharts";
import { api } from "./services/api";
import type { Batch, Forecast, Product, TelemetryReading } from "./types";

const NAV = [
  ["Overview", LayoutDashboard],
  ["Batches", Boxes],
  ["FEFO Queue", Package],
  ["Telemetry", Activity],
  ["Forecasting", ShieldAlert],
] as const;

type Page = (typeof NAV)[number][0];

function App() {
  const [page, setPage] = useState<Page>("Overview");
  const [products, setProducts] = useState<Product[]>([]);
  const [batches, setBatches] = useState<Batch[]>([]);
  const [fefoBatches, setFefoBatches] = useState<Batch[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [forecast, setForecast] = useState<Forecast | null>(null);
  const [telemetry, setTelemetry] = useState<TelemetryReading[]>([]);
  const [healthy, setHealthy] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [error, setError] = useState("");
  const [mobile, setMobile] = useState(false);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [p, b, f, h] = await Promise.all([
        api.products(), api.batches(), api.fefo(), api.health()
      ]);
      setProducts(p);
      setBatches(b);
      setFefoBatches(f);
      setHealthy(h.status === "ok");
      setSelected(current => current ?? b[0]?.id ?? null);
    } catch (e) {
      setHealthy(false);
      setError(e instanceof Error ? e.message : "Could not connect to API");
    } finally {
      setLoading(false);
    }
  };

  const loadDetails = async (id: number) => {
    setDetailsLoading(true);
    try {
      const [f, t] = await Promise.all([api.forecast(id), api.telemetry(id)]);
      setForecast(f);
      setTelemetry(t);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to load batch details");
      setForecast(null);
      setTelemetry([]);
    } finally {
      setDetailsLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);
  useEffect(() => {
    if (selected !== null) void loadDetails(selected);
  }, [selected]);

  const productMap = useMemo(() => new Map(products.map(p => [p.id, p])), [products]);
  const totalKg = batches.reduce((sum, b) => sum + b.quantity_kg, 0);
  const activeBatches = batches.filter(b => ["in_storage", "in_transit"].includes(b.current_status));
  const urgentBatches = fefoBatches.filter(b => daysUntil(b.expiry_date) <= 2);
  const selectedBatch = batches.find(b => b.id === selected) ?? null;
  const risk = forecast?.spoilage_risk_score ?? 0;
  const riskLabel = risk >= 0.7 ? "High" : risk >= 0.35 ? "Moderate" : "Low";

  const selectBatch = (id: number) => setSelected(id);

  return (
    <div className="shell">
      <aside className={`side ${mobile ? "open" : ""}`}>
        <div className="brand">
          <div className="brandIcon"><Factory size={19} /></div>
          <div><b>FreshTrack</b><small>Inventory Intelligence</small></div>
          <button className="close" onClick={() => setMobile(false)}><X /></button>
        </div>
        <div className="plant">
          PLANT / WAREHOUSE
          <button>Main Warehouse <ChevronDown size={14} /></button>
        </div>
        <nav>
          {NAV.map(([name, Icon]) => (
            <button className={page === name ? "active" : ""} onClick={() => { setPage(name); setMobile(false); }} key={name}>
              <Icon size={17} />{name}
            </button>
          ))}
        </nav>
        <div className="sideBottom">
          <div className="apiState">
            <span className={healthy ? "ok" : "bad"}></span>
            <div><b>FastAPI</b><small>{healthy === null ? "Checking..." : healthy ? "Connected" : "Offline"}</small></div>
          </div>
          <button><Settings size={17} />Settings</button>
        </div>
      </aside>

      <main>
        <header>
          <button className="menu" onClick={() => setMobile(true)}><Menu /></button>
          <div className="crumb">Main Warehouse <span>/</span> {page}</div>
          <div className="headRight">
            <span className={healthy ? "live" : "offline"}><i /> {healthy ? "API Live" : "API Offline"}</span>
            <button onClick={() => void load()} title="Refresh"><RefreshCw size={17} /></button>
            <div className="avatar">FT</div>
          </div>
        </header>

        <section className="content">
          <div className="titleRow">
            <div>
              <small>PERISHABLE FOOD INVENTORY</small>
              <h1>{page}</h1>
              <p>Demand, shelf-life and telemetry intelligence from your FastAPI backend.</p>
            </div>
            {selectedBatch && <div className="selectedBadge"><span>Selected</span><b>#{selectedBatch.id} · {productMap.get(selectedBatch.product_id)?.name}</b></div>}
          </div>

          {error && <div className="error"><AlertTriangle size={16} />{error}<button onClick={() => void load()}>Retry</button></div>}

          {loading ? <div className="loading">Connecting to FastAPI…</div> : (
            <>
              {page === "Overview" && (
                <Overview
                  products={products} batches={batches} activeBatches={activeBatches} totalKg={totalKg}
                  urgentBatches={urgentBatches} productMap={productMap} selected={selected}
                  setSelected={selectBatch} forecast={forecast} telemetry={telemetry} risk={risk}
                  riskLabel={riskLabel} detailsLoading={detailsLoading}
                />
              )}
              {page === "Batches" && (
                <BatchesPage batches={batches} productMap={productMap} selected={selected} setSelected={selectBatch} />
              )}
              {page === "FEFO Queue" && (
                <FEFOPage batches={fefoBatches} productMap={productMap} selected={selected} setSelected={selectBatch} />
              )}
              {page === "Telemetry" && (
                <TelemetryPage batches={batches} productMap={productMap} selected={selected} setSelected={selectBatch} telemetry={telemetry} />
              )}
              {page === "Forecasting" && (
                <ForecastPage batches={batches} productMap={productMap} selected={selected} setSelected={selectBatch} forecast={forecast} detailsLoading={detailsLoading} />
              )}
            </>
          )}
        </section>
      </main>
    </div>
  );
}

function Overview({ products, batches, activeBatches, totalKg, urgentBatches, productMap, selected, setSelected, forecast, telemetry, risk, riskLabel, detailsLoading }: any) {
  return <>
    <BatchSelector
      batches={batches}
      productMap={productMap}
      selected={selected}
      setSelected={setSelected}
    />
    <div className="kpis"></div>
    <div className="kpis">
      <K label="Products" value={products.length} icon={<Boxes size={16} />} />
      <K label="Active batches" value={activeBatches.length} icon={<Package size={16} />} />
      <K label="Inventory" value={`${totalKg.toLocaleString()} kg`} icon={<Gauge size={16} />} />
      <K label="FEFO urgent" value={urgentBatches.length} danger={urgentBatches.length > 0} icon={<Clock3 size={16} />} />
    </div>
    <div className="grid">
      <section className="card large">
        <Head title="Batch Inventory" sub="Live records returned by GET /batches" />
        <BatchTable batches={batches} productMap={productMap} selected={selected} setSelected={setSelected} />
      </section>
      <section className="card">
        <Head title="Selected Batch Risk" sub="Forecast calculated by /batches/{id}/forecast" />
        {detailsLoading ? <div className="empty compact">Loading batch intelligence…</div> : <Risk forecast={forecast} label={riskLabel} risk={risk} />}
        <div className="mini"><span>Remaining shelf life</span><b>{forecast ? `${forecast.remaining_shelf_life_days} days` : "—"}</b></div>
        <div className="mini"><span>Predicted waste</span><b>{forecast ? `${forecast.predicted_waste_units} units` : "—"}</b></div>
        <div className="mini"><span>Production recommendation</span><b>{forecast ? `${forecast.production_recommendation} units` : "—"}</b></div>
        <div className="mini"><span>Dynamic reorder point</span><b>{forecast ? forecast.dynamic_rop : "—"}</b></div>
      </section>
    </div>
    <div className="grid">
      <TelemetryChart rows={telemetry} />
      <ForecastChart forecast={forecast} />
    </div>
  </>;
}

function BatchesPage({ batches, productMap, selected, setSelected }: any) {
  return <section className="card"><Head title="All Batches" sub="Operational batch records from GET /batches" /><BatchTable batches={batches} productMap={productMap} selected={selected} setSelected={setSelected} /></section>;
}

function FEFOPage({ batches, productMap, selected, setSelected }: any) {
  const ordered = [...batches].sort((a, b) => new Date(a.expiry_date).getTime() - new Date(b.expiry_date).getTime());
  return <>
    <div className="fefoIntro card">
      <div className="fefoIcon"><Package size={20} /></div>
      <div><h2>First Expired, First Out</h2><p>Prioritize batches by earliest expiry so stock with the shortest remaining life moves first.</p></div>
      <div className="fefoStat"><b>{ordered.length}</b><span>queued batches</span></div>
    </div>
    <section className="card"><Head title="FEFO Priority Queue" sub="Backend order from GET /batches/fefo, displayed by expiry priority" />
      <div className="queueList">
        {ordered.map((b, i) => {
          const days = daysUntil(b.expiry_date);
          const urgency = days < 0 ? "Expired" : days <= 1 ? "Critical" : days <= 2 ? "Urgent" : days <= 4 ? "Soon" : "Normal";
          return <button className={`queueItem ${selected === b.id ? "selected" : ""}`} key={b.id} onClick={() => setSelected(b.id)}>
            <div className="rank">{i + 1}</div>
            <div className="queueMain"><b>{productMap.get(b.product_id)?.name ?? `Product #${b.product_id}`}</b><span>Batch #{b.id} · {b.quantity_kg} kg</span></div>
            <div className="expiry"><span>{b.expiry_date}</span><b className={`urgency ${urgency.toLowerCase()}`}>{urgency}</b></div>
            <div className="days">{days < 0 ? `${Math.abs(days)}d overdue` : `${days}d left`}<ArrowUpRight size={14} /></div>
          </button>;
        })}
        {!ordered.length && <div className="empty">No batches are currently eligible for FEFO.</div>}
      </div>
    </section>
  </>;
}

function TelemetryPage({ batches, productMap, selected, setSelected, telemetry }: any) {
  return <>
    <BatchSelector batches={batches} productMap={productMap} selected={selected} setSelected={setSelected} />
    <TelemetryChart rows={telemetry} detailed />
  </>;
}

function ForecastPage({ batches, productMap, selected, setSelected, forecast, detailsLoading }: any) {
  return <>
    <BatchSelector batches={batches} productMap={productMap} selected={selected} setSelected={setSelected} />
    {detailsLoading ? <div className="loading">Loading forecast…</div> : <>
      <div className="forecastSummary">
        <Metric icon={<ShieldAlert size={17} />} label="Spoilage risk" value={forecast ? `${Math.round(forecast.spoilage_risk_score * 100)}%` : "—"} />
        <Metric icon={<Clock3 size={17} />} label="Shelf life" value={forecast ? `${forecast.remaining_shelf_life_days} days` : "—"} />
        <Metric icon={<Package size={17} />} label="Predicted waste" value={forecast ? `${forecast.predicted_waste_units}` : "—"} />
        <Metric icon={<Factory size={17} />} label="Production recommendation" value={forecast ? `${forecast.production_recommendation}` : "—"} />
      </div>
      <ForecastChart forecast={forecast} detailed />
      {forecast?.model_evaluation && <ModelEvaluation evaluation={forecast.model_evaluation} />}
    </>}
  </>;
}

function BatchSelector({ batches, productMap, selected, setSelected }: any) {
  return <div className="selector card">
    <div><small>ANALYZE BATCH</small><b>Select a batch</b></div>
    <select value={selected ?? ""} onChange={e => setSelected(Number(e.target.value))}>
      {batches.map((b: Batch) => <option key={b.id} value={b.id}>#{b.id} · {productMap.get(b.product_id)?.name ?? `Product #${b.product_id}`} · {b.quantity_kg} kg</option>)}
    </select>
  </div>;
}

function BatchTable({ batches, productMap, selected, setSelected }: any) {
  return <div className="tableWrap"><table><thead><tr><th>ID</th><th>Product</th><th>Quantity</th><th>Production</th><th>Expiry</th><th>Status</th></tr></thead>
    <tbody>{batches.map((b: Batch) => <tr className={selected === b.id ? "sel" : ""} onClick={() => setSelected(b.id)} key={b.id}>
      <td><b>#{b.id}</b></td><td>{productMap.get(b.product_id)?.name ?? `Product #${b.product_id}`}</td><td>{b.quantity_kg} kg</td><td>{b.production_date}</td><td>{b.expiry_date}</td><td><span className={`tag ${b.current_status}`}>{b.current_status}</span></td>
    </tr>)}</tbody></table>{!batches.length && <div className="empty">No batches returned by the backend.</div>}</div>;
}

function Risk({ forecast, label, risk }: any) {
  return <div className="risk"><div className={`riskCircle ${label.toLowerCase()}`}><strong>{Math.round(risk * 100)}%</strong><small>{label} risk</small></div><div><b>{forecast?.product_name ?? "Select a batch"}</b><p>{forecast?.predicted_temperature_c != null ? `Predicted temperature ${forecast.predicted_temperature_c}°C` : "No forecast loaded"}</p><small>{forecast?.forecast_method ?? ""}</small></div></div>;
}

function TelemetryChart({ rows, detailed = false }: { rows: TelemetryReading[]; detailed?: boolean }) {
  const data = rows.map(r => ({
    time: new Date(r.time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    temperature: r.temperature_c,
    humidity: r.humidity,
    risk: r.spoilage_risk_score == null ? null : Math.round(r.spoilage_risk_score * 100)
  }));
  return <section className={`card chart ${detailed ? "detailed" : ""}`}>
    <Head title="Environmental Telemetry" sub="GET /batches/{id}/telemetry" />
    <div className="legendCards"><span><Thermometer size={14} />Temperature (°C)</span><span><Droplets size={14} />Humidity (%)</span><span><ShieldAlert size={14} />Spoilage risk (%)</span></div>
    {data.length ? <ResponsiveContainer width="100%" height={detailed ? 330 : 260}><LineChart data={data}><CartesianGrid strokeDasharray="3 3" vertical={false}/><XAxis dataKey="time"/><YAxis
  yAxisId="env"
  label={{ value: "Temperature / Humidity", angle: -90, position: "insideLeft" }}
/>
<YAxis
  yAxisId="risk"
  orientation="right"
  domain={[0, 100]}
  label={{ value: "Risk (%)", angle: 90, position: "insideRight" }}
/>
<Tooltip/><Legend/>
  <Line
    yAxisId="env"
    type="monotone"
    dataKey="temperature"
    name="Temperature °C"
    connectNulls
    stroke="#2563eb"
    strokeWidth={2}
  />
<Line
  yAxisId="env"
  type="monotone"
  dataKey="humidity"
  name="Humidity %"
  connectNulls
  stroke="#16a34a"
  strokeWidth={2}
/>
<Line
  yAxisId="risk"
  type="monotone"
  dataKey="risk"
  name="Spoilage Risk %"
  connectNulls
  stroke="#dc2626"
  strokeWidth={2}
/>
</LineChart></ResponsiveContainer> : <div className="empty">No telemetry readings for the selected batch.</div>}
  </section>;
}

function ForecastChart({ forecast, detailed = false }: { forecast: Forecast | null; detailed?: boolean }) {
  const data = forecast?.burnout_timeline ?? [];
  return <section className={`card chart ${detailed ? "detailed" : ""}`}><Head title="7-Day Demand & Burnout" sub="Demand forecast and remaining stock from the forecasting engine"/>
    {data.length ? <ResponsiveContainer width="100%" height={detailed ? 330 : 260}><BarChart data={data}><CartesianGrid strokeDasharray="3 3" vertical={false}/><XAxis dataKey="day" tickFormatter={v => `D${v}`}/><YAxis/><Tooltip/><Legend/><ReferenceLine y={0}/>
<Bar
  dataKey="predicted_demand"
  name="Predicted Demand"
  fill="#2563eb"
/>
<Bar
  dataKey="dynamic_spoilage"
  name="Dynamic Spoilage"
  fill="#dc2626"
/>
</BarChart></ResponsiveContainer> : <div className="empty">No forecast loaded for the selected batch.</div>}
    {detailed && forecast && <div className="forecastMeta"><span>Method <b>{forecast.forecast_method}</b></span><span>Samples <b>{forecast.sample_count}</b></span><span>Lead time <b>{forecast.lead_time_days} days</b></span><span>Dynamic ROP <b>{forecast.dynamic_rop}</b></span></div>}
  </section>;
}

function ModelEvaluation({ evaluation }: any) {
  return <section className="card model"><Head title="Model Evaluation" sub={`Test period: ${evaluation.test_period_days} days`} /><div className="modelGrid"><Metric label="MAE" value={evaluation.mae}/><Metric label="W-MAPE" value={evaluation.wmape}/><Metric label="Forecast bias" value={evaluation.forecast_bias}/><Metric label="Pinball q50" value={evaluation.pinball_loss_q50}/></div></section>;
}

function Metric({ label, value, icon }: { label: string; value: any; icon?: ReactNode }) { return <div className="metric">{icon && <span>{icon}</span>}<small>{label}</small><b>{value}</b></div>; }
function K({ label, value, danger = false, icon }: { label: string; value: any; danger?: boolean; icon?: ReactNode }) { return <div className="card k"><div className="kTop"><small>{label}</small>{icon}</div><b className={danger ? "danger" : ""}>{value}</b></div>; }
function Head({ title, sub }: { title: string; sub: string }) { return <div className="head"><div><h2>{title}</h2><p>{sub}</p></div></div>; }
function daysUntil(date: string) { const today = new Date(); today.setHours(0,0,0,0); const target = new Date(date); target.setHours(0,0,0,0); return Math.ceil((target.getTime() - today.getTime()) / 86400000); }

export default App;
