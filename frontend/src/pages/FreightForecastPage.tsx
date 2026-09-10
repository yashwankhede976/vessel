import { useMemo, useState } from "react";
import PageHeader from "../components/layout/PageHeader";
import { Card, ChartContainer, FormField, Loading, Table } from "../components/ui";
import type { Column } from "../components/ui";
import { DataLabel, LineChart } from "../components/domain";
import type { ChartSeries, ConfidenceBand } from "../components/domain";
import { api, ApiError } from "../api";
import type { FreightForecastPoint, FreightForecastResponse } from "../api";
import { formatCurrency } from "../lib/format";
import "./FreightForecastPage.css";

/**
 * Freight Forecast: lane selectors → the composed GET /forecasts/freight/
 * endpoint (historical observations + model forecast + confidence band). The
 * forecast series is clearly labelled FORECAST; historical points carry their
 * REAL/ESTIMATED provenance.
 */
const ORIGINS = ["Australia", "Indonesia", "Mozambique", "USA", "Russia"];
const DESTINATIONS = ["Paradip", "Dhamra", "Visakhapatnam", "Gangavaram", "Gopalpur", "Haldia"];
const VESSEL_TYPES = ["capesize", "panamax", "kamsarmax", "supramax", "ultramax", "handysize"];

const dayIndex = (iso: string, base: number) =>
  Math.round((new Date(iso).getTime() - base) / 86_400_000);

export default function FreightForecastPage() {
  const [origin, setOrigin] = useState(ORIGINS[0]);
  const [destination, setDestination] = useState(DESTINATIONS[0]);
  const [vesselType, setVesselType] = useState("");
  const [historyDays, setHistoryDays] = useState("180");
  const [data, setData] = useState<FreightForecastResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.analytics.freightForecast({
        origin,
        destination,
        vessel_type: vesselType || undefined,
        history_days: Number(historyDays) || 180,
      });
      setData(res);
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError("network", "Unexpected error."));
    } finally {
      setLoading(false);
    }
  };

  const { series, band, xLabels } = useMemo(() => {
    if (!data || (data.historical.length === 0 && data.forecast.length === 0)) {
      return { series: [] as ChartSeries[], band: undefined, xLabels: [] as string[] };
    }
    const allDates = [
      ...data.historical.map((h) => h.date),
      ...data.forecast.map((f) => f.target_date),
    ].sort();
    const base = new Date(allDates[0]).getTime();

    const histSeries: ChartSeries = {
      name: "Historical",
      color: "#16374f",
      points: data.historical.map((h) => ({ x: dayIndex(h.date, base), y: Number(h.rate_per_tonne) })),
    };
    const fcSeries: ChartSeries = {
      name: "Forecast",
      color: "#0e7c86",
      dashed: true,
      points: data.forecast.map((f) => ({
        x: dayIndex(f.target_date, base),
        y: Number(f.predicted_rate_per_tonne),
      })),
    };
    const hasBand = data.forecast.some((f) => f.lower_bound && f.upper_bound);
    const cband: ConfidenceBand | undefined = hasBand
      ? {
          lower: data.forecast.map((f) => ({
            x: dayIndex(f.target_date, base),
            y: Number(f.lower_bound ?? f.predicted_rate_per_tonne),
          })),
          upper: data.forecast.map((f) => ({
            x: dayIndex(f.target_date, base),
            y: Number(f.upper_bound ?? f.predicted_rate_per_tonne),
          })),
        }
      : undefined;

    const uniqueX = Array.from(
      new Set([...histSeries.points, ...fcSeries.points].map((p) => p.x)),
    ).sort((a, b) => a - b);
    const labels = uniqueX.map((x) => {
      const d = new Date(base + x * 86_400_000);
      return `${d.getMonth() + 1}/${d.getDate()}`;
    });

    const out = [histSeries, fcSeries].filter((s) => s.points.length > 0);
    return { series: out, band: cband, xLabels: labels };
  }, [data]);

  const forecastColumns: Column<FreightForecastPoint>[] = [
    { key: "target_date", header: "Target date" },
    { key: "horizon", header: "Horizon" },
    {
      key: "predicted_rate_per_tonne",
      header: "Forecast / t",
      align: "right",
      render: (r) => formatCurrency(r.predicted_rate_per_tonne, r.currency),
    },
    {
      key: "band",
      header: "Confidence band",
      align: "right",
      render: (r) =>
        r.lower_bound && r.upper_bound
          ? `${formatCurrency(r.lower_bound, r.currency)} – ${formatCurrency(r.upper_bound, r.currency)}`
          : "—",
    },
    {
      key: "confidence",
      header: "Confidence",
      align: "right",
      render: (r) => (r.confidence != null ? `${Math.round(Number(r.confidence) * 100)}%` : "—"),
    },
  ];

  const noData = data && data.forecast.length === 0 && data.historical.length === 0;

  return (
    <>
      <PageHeader
        title="Freight Forecast"
        description="Historical freight rates and the model forecast with confidence bands for a selected lane. Forecast points are model output (FORECAST)."
        actions={
          <button className="btn btn--primary" onClick={run} disabled={loading}>
            {loading ? "Loading…" : "Load forecast"}
          </button>
        }
      />

      <Card title="Lane" subtitle="Origin → East Coast India destination">
        <div className="forecast-filters">
          <FormField label="Origin">
            {(id) => (
              <select id={id} className="ui-field__input" value={origin} onChange={(e) => setOrigin(e.target.value)}>
                {ORIGINS.map((o) => <option key={o} value={o}>{o}</option>)}
              </select>
            )}
          </FormField>
          <FormField label="Destination">
            {(id) => (
              <select id={id} className="ui-field__input" value={destination} onChange={(e) => setDestination(e.target.value)}>
                {DESTINATIONS.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            )}
          </FormField>
          <FormField label="Vessel type" hint="Optional">
            {(id) => (
              <select id={id} className="ui-field__input" value={vesselType} onChange={(e) => setVesselType(e.target.value)}>
                <option value="">Any</option>
                {VESSEL_TYPES.map((v) => <option key={v} value={v}>{v}</option>)}
              </select>
            )}
          </FormField>
          <FormField
            label="History (days)"
            type="number"
            value={historyDays}
            onChange={setHistoryDays}
          />
        </div>
      </Card>

      <ChartContainer
        title={
          <span className="forecast-chart-title">
            Freight rate — {origin} → {destination} <DataLabel kind="FORECAST" />
          </span>
        }
        height={320}
        loading={loading}
        error={!!error}
        onRetry={run}
      >
        {noData ? (
          <p className="forecast-empty">
            {data?.message ?? "No route/forecast data for this lane yet."}
          </p>
        ) : series.length > 0 ? (
          <LineChart series={series} band={band} xLabels={xLabels} height={300} yLabel="rate/t" />
        ) : (
          <p className="forecast-empty">Load a lane to view its forecast.</p>
        )}
      </ChartContainer>

      {loading ? (
        <Card><Loading fill /></Card>
      ) : data && data.forecast.length > 0 ? (
        <Card title="Forecast points" padded={false}>
          <Table
            columns={forecastColumns}
            rows={data.forecast}
            rowKey={(r) => `${r.target_date}-${r.horizon}`}
          />
        </Card>
      ) : null}
    </>
  );
}
