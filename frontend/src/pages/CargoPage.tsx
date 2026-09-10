import { useState } from "react";
import PageHeader from "../components/layout/PageHeader";
import { Badge, Card, ErrorState, FormField, Loading, Table } from "../components/ui";
import type { Column } from "../components/ui";
import { DataLabel } from "../components/domain";
import { api, ApiError } from "../api";
import type { LandedCostInput } from "../api/endpoints/analytics";
import type { OriginComparison, OriginComparisonEntry } from "../api";
import { formatMoney } from "../lib/format";
import "./CargoPage.css";

/**
 * Cargo & sourcing: compare the delivered (landed) cost of a commodity into a
 * destination across the project origins, using the backend landed-cost
 * comparator. Inputs are per-origin cost components; the backend returns the
 * cheapest-first ranking with the delta vs cheapest.
 */
const ORIGINS = ["Australia", "Indonesia", "Mozambique", "USA", "Russia"];
const DESTINATIONS = ["Paradip", "Dhamra", "Visakhapatnam", "Gangavaram", "Gopalpur", "Haldia"];

interface OriginCost {
  origin: string;
  commodity_cost: string;
  freight_cost: string;
  port_charges: string;
}

const DEFAULT_COSTS: OriginCost[] = [
  { origin: "Australia", commodity_cost: "5000000", freight_cost: "1200000", port_charges: "150000" },
  { origin: "Indonesia", commodity_cost: "4800000", freight_cost: "900000", port_charges: "150000" },
  { origin: "Mozambique", commodity_cost: "5100000", freight_cost: "1400000", port_charges: "150000" },
];

export default function CargoPage() {
  const [destination, setDestination] = useState(DESTINATIONS[0]);
  const [cargoTonnes, setCargoTonnes] = useState("50000");
  const [costs, setCosts] = useState<OriginCost[]>(DEFAULT_COSTS);
  const [result, setResult] = useState<OriginComparison | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const update = (idx: number, key: keyof OriginCost, value: string) =>
    setCosts((cs) => cs.map((c, i) => (i === idx ? { ...c, [key]: value } : c)));

  const compare = async () => {
    setLoading(true);
    setError(null);
    try {
      const inputs: LandedCostInput[] = costs.map((c) => ({
        origin: c.origin,
        destination,
        cargo_tonnes: cargoTonnes,
        commodity_cost: { amount: c.commodity_cost, currency: "USD" },
        freight_cost: { amount: c.freight_cost, currency: "USD" },
        port_charges: { amount: c.port_charges, currency: "USD" },
        target_currency: "USD",
      }));
      setResult(await api.analytics.compareOrigins(inputs));
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError("network", "Unexpected error."));
    } finally {
      setLoading(false);
    }
  };

  const columns: Column<OriginComparisonEntry>[] = [
    { key: "origin", header: "Origin", render: (e) => (
      <span>{e.origin} {e.is_cheapest && <Badge variant="success">Cheapest</Badge>}</span>
    ) },
    { key: "total_landed_cost", header: "Total landed cost", align: "right", render: (e) => formatMoney(e.total_landed_cost) },
    { key: "landed_cost_per_tonne", header: "Per tonne", align: "right", render: (e) => formatMoney(e.landed_cost_per_tonne) },
    { key: "delta_vs_cheapest", header: "Δ vs cheapest", align: "right", render: (e) => formatMoney(e.delta_vs_cheapest) },
  ];

  return (
    <>
      <PageHeader
        title="Cargo & Sourcing"
        description="Compare total landed cost across origins for a destination. All-in delivered cost (commodity + freight + port + …) ranked cheapest-first by the backend."
        actions={
          <button className="btn btn--primary" onClick={compare} disabled={loading}>
            {loading ? "Comparing…" : "Compare origins"}
          </button>
        }
      />

      <Card title="Requirement">
        <div className="cargo-req">
          <FormField label="Destination">
            {(id) => (
              <select id={id} className="ui-field__input" value={destination} onChange={(e) => setDestination(e.target.value)}>
                {DESTINATIONS.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            )}
          </FormField>
          <FormField label="Cargo (tonnes)" type="number" value={cargoTonnes} onChange={setCargoTonnes} />
        </div>
      </Card>

      <Card title="Origin cost components" subtitle="USD totals per origin" padded={false}>
        <div className="cargo-costs">
          <div className="cargo-costs__head">
            <span>Origin</span><span>Commodity</span><span>Freight</span><span>Port charges</span>
          </div>
          {costs.map((c, idx) => (
            <div className="cargo-costs__row" key={c.origin}>
              <select className="ui-field__input" value={c.origin} onChange={(e) => update(idx, "origin", e.target.value)}>
                {ORIGINS.map((o) => <option key={o} value={o}>{o}</option>)}
              </select>
              <input className="ui-field__input" type="number" value={c.commodity_cost} onChange={(e) => update(idx, "commodity_cost", e.target.value)} />
              <input className="ui-field__input" type="number" value={c.freight_cost} onChange={(e) => update(idx, "freight_cost", e.target.value)} />
              <input className="ui-field__input" type="number" value={c.port_charges} onChange={(e) => update(idx, "port_charges", e.target.value)} />
            </div>
          ))}
        </div>
      </Card>

      {loading ? (
        <Card><Loading fill /></Card>
      ) : error ? (
        <Card><ErrorState onRetry={compare} message={error.displayMessage} /></Card>
      ) : result ? (
        <Card title={`Landed cost into ${result.destination}`} subtitle="Cheapest first" padded={false}
          actions={<DataLabel kind="ESTIMATED" />}>
          <Table columns={columns} rows={result.entries} rowKey={(e) => e.origin} />
        </Card>
      ) : null}
    </>
  );
}
