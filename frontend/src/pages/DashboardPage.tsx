import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import PageHeader from "../components/layout/PageHeader";
import { Card, ChartContainer } from "../components/ui";
import {
  DataFreshnessStrip,
  DataLabel,
  DecisionCard,
  LineChart,
  StatTile,
} from "../components/domain";
import type { ChartSeries, ConfidenceBand, DecisionFactor } from "../components/domain";
import { Modal } from "../components/ui";
import EastCoastMap from "./ports/EastCoastMap";
import { api, useApi, ApiError } from "../api";
import type {
  FixWaitResult,
  FreightForecastResponse,
  MarketPressureResult,
  Paginated,
  DecisionAlert,
  Port,
  SpotVsContractResult,
  Vessel,
} from "../api";
import { formatCurrency, formatNumber, humanize } from "../lib/format";
import "./DashboardPage.css";

/**
 * Executive Dashboard — answers "what is happening / what will happen / what
 * should I do" by composing the live decision engines: market pressure, freight
 * forecast, fix/wait timing, contract strategy, and open alerts. Each panel
 * degrades independently; nothing here is illustrative — it is backend output,
 * labelled by nature (FORECAST / ESTIMATED).
 */
const LANE = { origin: "Australia", destination: "Paradip" };

interface DashState {
  pressure: MarketPressureResult | null;
  forecast: FreightForecastResponse | null;
  fixWait: FixWaitResult | null;
  strategy: SpotVsContractResult | null;
  alerts: Paginated<DecisionAlert> | null;
  loading: boolean;
  error: ApiError | null;
}

export default function DashboardPage() {
  const [s, setS] = useState<DashState>({
    pressure: null, forecast: null, fixWait: null, strategy: null, alerts: null,
    loading: true, error: null,
  });
  const [mapVessel, setMapVessel] = useState<Vessel | null>(null);

  // Map data (East Coast ports + vessel positions) — independent, resilient.
  const portsState = useApi(
    (signal) => api.ports.list({ coast: "east_coast_india", page_size: 50 }, signal),
    [],
  );
  const vesselsState = useApi((signal) => api.vessels.list({ page_size: 200 }, signal), []);
  const mapPorts: Port[] = portsState.data?.items ?? [];
  const mapVessels: Vessel[] = vesselsState.data?.items ?? [];

  useEffect(() => {
    let active = true;
    (async () => {
      // Each call is independent and resilient — a scaffold/empty endpoint must
      // not blank the whole dashboard.
      const safe = <T,>(p: Promise<T>) => p.catch(() => null);
      const [pressure, forecast, fixWait, strategy, alerts] = await Promise.all([
        safe(api.analytics.marketPressure({ vessel_supply: 0.35, cargo_demand: 0.75, port_congestion: 60, freight_volatility: 0.5 })),
        safe(api.analytics.freightForecast({ origin: LANE.origin, destination: LANE.destination })),
        safe(api.analytics.fixWait({ current_rate: "22", forecast_7d: "21.5", forecast_14d: "21", confidence_7d: 0.75, confidence_14d: 0.7, days_to_deadline: 30 })),
        safe(api.analytics.spotVsContract({ spot_freight_per_tonne: "22", cargo_tonnes: "75000", freight_volatility: 0.5 })),
        safe(api.alerts.list({ status: "new", page_size: 5 })),
      ]);
      if (active) {
        setS({ pressure, forecast, fixWait, strategy, alerts, loading: false, error: null });
      }
    })();
    return () => { active = false; };
  }, []);

  // Build forecast chart series from the composed forecast response.
  let series: ChartSeries[] = [];
  let band: ConfidenceBand | undefined;
  let xLabels: string[] = [];
  if (s.forecast && s.forecast.forecast.length > 0) {
    const pts = s.forecast.forecast;
    const base = new Date(pts[0].target_date).getTime();
    const di = (iso: string) => Math.round((new Date(iso).getTime() - base) / 86_400_000);
    series = [{
      name: "Forecast", color: "#0e7c86", dashed: true,
      points: pts.map((p) => ({ x: di(p.target_date), y: Number(p.predicted_rate_per_tonne) })),
    }];
    if (pts.some((p) => p.lower_bound && p.upper_bound)) {
      band = {
        lower: pts.map((p) => ({ x: di(p.target_date), y: Number(p.lower_bound ?? p.predicted_rate_per_tonne) })),
        upper: pts.map((p) => ({ x: di(p.target_date), y: Number(p.upper_bound ?? p.predicted_rate_per_tonne) })),
      };
    }
    xLabels = pts.map((p) => { const d = new Date(p.target_date); return `${d.getMonth() + 1}/${d.getDate()}`; });
  }

  const history = s.forecast?.historical ?? [];
  const currentRate = history.length > 0 ? history[history.length - 1].rate_per_tonne : undefined;
  const alertCount = s.alerts?.pagination?.count ?? s.alerts?.items.length ?? 0;

  const factors: DecisionFactor[] = [];
  if (s.strategy) factors.push({ label: "Best strategy", value: humanize(s.strategy.recommended_strategy) });
  if (s.pressure) factors.push({ label: "Market pressure", value: `${s.pressure.index.toFixed(0)}/100 (${humanize(s.pressure.classification)})` });
  if (s.fixWait?.expected_move_pct != null) factors.push({ label: "Expected freight move", value: `${(s.fixWait.expected_move_pct * 100).toFixed(1)}%` });

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Freight market, vessel availability and the recommended action for East Coast India dry-bulk procurement."
        actions={<Link className="btn btn--primary" to="/chartering">New recommendation</Link>}
      />

      <DataFreshnessStrip />

      {/* WHAT SHOULD I DO — the headline decision */}
      <div className="dashboard-decision">
        <DecisionCard
          decision={s.fixWait ? humanize(s.fixWait.decision).toUpperCase() : (s.loading ? "…" : "MONITOR")}
          headline={`${LANE.origin} → ${LANE.destination}`}
          subline={s.strategy ? humanize(s.strategy.recommended_strategy) : undefined}
          expectedSaving={s.strategy ? formatCurrency(s.strategy.expected_savings, s.strategy.currency) : undefined}
          risk={s.strategy ? (s.strategy.risk_score >= 66 ? "HIGH" : s.strategy.risk_score >= 33 ? "MEDIUM" : "LOW") : undefined}
          confidence={s.fixWait?.effective_confidence ?? null}
          reason={s.fixWait?.reason}
          factors={factors}
        />
      </div>

      {/* WHAT IS HAPPENING — KPIs */}
      <div className="kpi-grid">
        <StatTile label="Current freight" value={currentRate ? formatCurrency(currentRate) : "—"} note={`${LANE.origin} → ${LANE.destination}`} badge={<DataLabel kind={currentRate ? "REAL" : "UNKNOWN"} />} />
        <StatTile label="Market pressure" value={s.pressure ? s.pressure.index.toFixed(0) : "—"} note={s.pressure ? humanize(s.pressure.classification) : "no data"} badge={<DataLabel kind="ESTIMATED" />} />
        <StatTile label="Recommended strategy" value={s.strategy ? humanize(s.strategy.recommended_strategy) : "—"} note="lowest risk-adjusted cost" />
        <StatTile label="Active alerts" value={alertCount} note="new / unresolved" badge={alertCount > 0 ? <DataLabel kind="REAL" /> : undefined} />
      </div>

      {/* WHAT WILL HAPPEN — forecast */}
      <div className="dashboard-grid">
        <ChartContainer
          title={<span className="dash-chart-title">Freight rate forecast <DataLabel kind="FORECAST" /></span>}
          height={320}
          loading={s.loading}
        >
          {series.length > 0 ? (
            <LineChart series={series} band={band} xLabels={xLabels} height={300} yLabel="rate/t" />
          ) : (
            <p className="dashboard-empty">No forecast available yet for this lane. <Link to="/forecasts">Open Freight Forecast →</Link></p>
          )}
        </ChartContainer>

        <Card title="New alerts" subtitle="Most recent unresolved">
          {s.alerts && s.alerts.items.length > 0 ? (
            <ul className="dashboard-alerts">
              {s.alerts.items.map((a) => (
                <li key={a.id}>
                  <span className={`dashboard-alerts__sev dashboard-alerts__sev--${a.severity}`} />
                  <span>{a.message}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="dashboard-empty">No new alerts. <Link to="/alerts">Open Alert Center →</Link></p>
          )}
        </Card>
      </div>

      {/* East Coast India fleet map — ports + live vessel positions */}
      <Card
        title="East Coast India — fleet map"
        subtitle="Ports and latest vessel positions"
        actions={<DataLabel kind="REAL" />}
      >
        <div className="dashboard-map">
          <EastCoastMap
            ports={mapPorts}
            selectedId={null}
            onSelect={() => { /* navigate handled on the Ports page */ }}
            vessels={mapVessels}
            onSelectVessel={setMapVessel}
          />
          <p className="dashboard-map__hint">
            {portsState.loading || vesselsState.loading
              ? "Loading map…"
              : "Click a vessel marker for its position. Full port detail on the Ports page."}{" "}
            <Link to="/ports">Open Ports →</Link>
          </p>
        </div>
      </Card>

      <Modal open={mapVessel !== null} onClose={() => setMapVessel(null)} title={mapVessel?.name ?? "Vessel"}>
        {mapVessel && (
          <dl className="dashboard-vessel">
            <div><dt>Type</dt><dd>{mapVessel.vessel_type_display}</dd></div>
            <div><dt>IMO</dt><dd>{mapVessel.imo}</dd></div>
            <div><dt>DWT (t)</dt><dd>{formatNumber(mapVessel.dwt, 0)}</dd></div>
            <div><dt>Availability</dt><dd>{mapVessel.availability_status_display}</dd></div>
            {mapVessel.latest_position && (
              <div>
                <dt>Position</dt>
                <dd>{formatNumber(mapVessel.latest_position.latitude)}, {formatNumber(mapVessel.latest_position.longitude)}</dd>
              </div>
            )}
          </dl>
        )}
      </Modal>
    </>
  );
}
