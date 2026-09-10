import { useState } from "react";
import PageHeader from "../components/layout/PageHeader";
import { Badge, Card, ErrorState, FormField, Loading, Table } from "../components/ui";
import type { Column } from "../components/ui";
import { api, useApi, ApiError } from "../api";
import type { IdleVesselResult, RankedOpportunity, Vessel } from "../api";
import { formatCurrency } from "../lib/format";
import "./IdleVesselsPage.css";

/**
 * Idle Vessel employment: pick an open vessel and rank candidate next voyages
 * by expected margin via the backend idle-vessel engine (revenue − cost −
 * ballast). The candidate opportunities are user-provided planning inputs.
 */
interface OppRow {
  name: string;
  laden_distance_nm: string;
  cargo_tonnes: string;
  freight_rate_per_tonne: string;
  ballast_distance_nm: string;
}

const DEFAULT_OPPS: OppRow[] = [
  { name: "Coal → Paradip", laden_distance_nm: "2000", cargo_tonnes: "55000", freight_rate_per_tonne: "18", ballast_distance_nm: "300" },
  { name: "Coal → Vizag", laden_distance_nm: "6000", cargo_tonnes: "55000", freight_rate_per_tonne: "20", ballast_distance_nm: "2500" },
];

export default function IdleVesselsPage() {
  const [vesselId, setVesselId] = useState<number | null>(null);
  const [opps, setOpps] = useState<OppRow[]>(DEFAULT_OPPS);
  const [result, setResult] = useState<IdleVesselResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  // Open vessels to choose from (real availability endpoint).
  const vesselsState = useApi((signal) => api.vessels.available({ page_size: 100 }, signal), []);
  const vessels = vesselsState.data?.items ?? [];

  const updateOpp = (idx: number, key: keyof OppRow, value: string) =>
    setOpps((os) => os.map((o, i) => (i === idx ? { ...o, [key]: value } : o)));

  const run = async () => {
    if (vesselId == null) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.analytics.idleVessel({
        vessel_id: vesselId,
        opportunities: opps.map((o) => ({
          name: o.name,
          laden_distance_nm: o.laden_distance_nm,
          cargo_tonnes: o.cargo_tonnes,
          freight_rate_per_tonne: o.freight_rate_per_tonne,
          ballast_distance_nm: o.ballast_distance_nm || null,
          bunker_price_per_tonne: "600",
        })),
      });
      setResult(res);
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError("network", "Unexpected error."));
    } finally {
      setLoading(false);
    }
  };

  const columns: Column<RankedOpportunity>[] = [
    { key: "name", header: "Opportunity" },
    { key: "expected_revenue", header: "Revenue", align: "right", render: (r) => formatCurrency(r.expected_revenue, r.currency) },
    { key: "expected_cost", header: "Cost", align: "right", render: (r) => formatCurrency(r.expected_cost, r.currency) },
    { key: "expected_margin", header: "Margin", align: "right", render: (r) => formatCurrency(r.expected_margin, r.currency) },
    { key: "voyage_days", header: "Days", align: "right", render: (r) => (r.voyage_days != null ? r.voyage_days.toFixed(1) : "—") },
    { key: "margin_per_day", header: "Margin/day", align: "right", render: (r) => (r.margin_per_day ? formatCurrency(r.margin_per_day, r.currency) : "—") },
  ];

  return (
    <>
      <PageHeader
        title="Idle Vessel Employment"
        description="Rank next-voyage opportunities for an open vessel by expected margin (revenue minus voyage and ballast cost), computed by the backend."
        actions={
          <button className="btn btn--primary" onClick={run} disabled={loading || vesselId == null}>
            {loading ? "Ranking…" : "Rank voyages"}
          </button>
        }
      />

      <Card title="Vessel">
        {vesselsState.loading ? (
          <Loading fill label="Loading open vessels…" />
        ) : vesselsState.error ? (
          <ErrorState onRetry={vesselsState.refetch} message={vesselsState.error.displayMessage} />
        ) : (
          <FormField label="Open vessel">
            {(id) => (
              <select
                id={id}
                className="ui-field__input"
                value={vesselId ?? ""}
                onChange={(e) => setVesselId(e.target.value ? Number(e.target.value) : null)}
              >
                <option value="">Select a vessel…</option>
                {vessels.map((v: Vessel) => (
                  <option key={v.id} value={v.id}>{v.name} — {v.vessel_type_display}</option>
                ))}
              </select>
            )}
          </FormField>
        )}
      </Card>

      <Card title="Candidate voyages" subtitle="Planning inputs" padded={false}>
        <div className="idle-opps">
          <div className="idle-opps__head">
            <span>Name</span><span>Laden nm</span><span>Cargo t</span><span>Freight/t</span><span>Ballast nm</span>
          </div>
          {opps.map((o, idx) => (
            <div className="idle-opps__row" key={idx}>
              <input className="ui-field__input" value={o.name} onChange={(e) => updateOpp(idx, "name", e.target.value)} />
              <input className="ui-field__input" type="number" value={o.laden_distance_nm} onChange={(e) => updateOpp(idx, "laden_distance_nm", e.target.value)} />
              <input className="ui-field__input" type="number" value={o.cargo_tonnes} onChange={(e) => updateOpp(idx, "cargo_tonnes", e.target.value)} />
              <input className="ui-field__input" type="number" value={o.freight_rate_per_tonne} onChange={(e) => updateOpp(idx, "freight_rate_per_tonne", e.target.value)} />
              <input className="ui-field__input" type="number" value={o.ballast_distance_nm} onChange={(e) => updateOpp(idx, "ballast_distance_nm", e.target.value)} />
            </div>
          ))}
        </div>
      </Card>

      {loading ? (
        <Card><Loading fill /></Card>
      ) : error ? (
        <Card><ErrorState onRetry={run} message={error.displayMessage} /></Card>
      ) : result ? (
        <>
          <Card title={`Ranked voyages for ${result.vessel_name}`} padded={false}>
            <Table columns={columns} rows={result.ranked_opportunities} rowKey={(r) => r.name} emptyMessage="No feasible voyages." />
          </Card>
          {result.excluded_opportunities.length > 0 && (
            <Card title="Excluded">
              <ul className="idle-excluded">
                {result.excluded_opportunities.map((o) => (
                  <li key={o.name}><Badge variant="danger">Infeasible</Badge> {o.name} — {o.notes.join(" ")}</li>
                ))}
              </ul>
            </Card>
          )}
        </>
      ) : null}
    </>
  );
}
