import { useState } from "react";
import PageHeader from "../components/layout/PageHeader";
import { Card, ErrorState, FormField, Loading, Table } from "../components/ui";
import type { Column } from "../components/ui";
import { StatTile } from "../components/domain";
import { api, ApiError } from "../api";
import type { CandidateVoyageInput } from "../api/endpoints/analytics";
import type { OptimizationResultDTO, SelectedVoyage } from "../api";
import { formatCurrency, humanize } from "../lib/format";
import "./OptimizerPage.css";

/**
 * Multi-voyage procurement optimizer: define candidate voyages + a requirement,
 * and the backend OR-Tools MILP returns the minimum-cost feasible allocation.
 * The frontend only sends candidates and renders the solver's plan.
 */
const DEFAULT_CANDIDATES: CandidateVoyageInput[] = [
  { id: "AUS-cape", origin: "Australia", destination: "Paradip", vessel_type: "capesize", contract_strategy: "SPOT", cost_per_voyage: "6200000", capacity_tonnes: "160000", max_voyages: 3 },
  { id: "IDN-pana", origin: "Indonesia", destination: "Paradip", vessel_type: "panamax", contract_strategy: "SPOT", cost_per_voyage: "2600000", capacity_tonnes: "75000", max_voyages: 5 },
  { id: "RUS-cape", origin: "Russia", destination: "Paradip", vessel_type: "capesize", contract_strategy: "MEDIUM_TERM", cost_per_voyage: "6400000", capacity_tonnes: "160000", max_voyages: 2 },
];

export default function OptimizerPage() {
  const [requiredTonnes, setRequiredTonnes] = useState("300000");
  const [tolerance, setTolerance] = useState("10");
  const [candidates, setCandidates] = useState<CandidateVoyageInput[]>(DEFAULT_CANDIDATES);
  const [result, setResult] = useState<OptimizationResultDTO | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const updateCandidate = (idx: number, key: keyof CandidateVoyageInput, value: string) =>
    setCandidates((cs) => cs.map((c, i) => (i === idx ? { ...c, [key]: value } : c)));

  const removeCandidate = (idx: number) =>
    setCandidates((cs) => cs.filter((_, i) => i !== idx));

  const addCandidate = () =>
    setCandidates((cs) => [
      ...cs,
      { id: `cand-${cs.length + 1}`, origin: "", destination: "Paradip", vessel_type: "panamax", contract_strategy: "SPOT", cost_per_voyage: "0", capacity_tonnes: "1", max_voyages: 1 },
    ]);

  const optimize = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.analytics.optimizeMultiVoyage({
        required_tonnes: requiredTonnes,
        candidates: candidates.map((c) => ({ ...c, max_voyages: Number(c.max_voyages) })),
        tolerance_pct: tolerance,
      });
      setResult(res);
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError("network", "Unexpected error."));
    } finally {
      setLoading(false);
    }
  };

  const selectedColumns: Column<SelectedVoyage>[] = [
    { key: "candidate_id", header: "Candidate" },
    { key: "origin", header: "Origin" },
    { key: "vessel_type", header: "Type", render: (r) => humanize(r.vessel_type) },
    { key: "contract_strategy", header: "Contract", render: (r) => humanize(r.contract_strategy) },
    { key: "voyages", header: "Voyages", align: "right" },
    { key: "tonnes", header: "Tonnes", align: "right", render: (r) => formatCurrency(r.tonnes, "").trim() },
    { key: "cost", header: "Cost", align: "right", render: (r) => formatCurrency(r.cost) },
  ];

  return (
    <>
      <PageHeader
        title="Optimizer"
        description="Minimum-cost multi-voyage procurement across candidate lanes, solved by the backend OR-Tools optimizer subject to capacity, compatibility and constraints."
        actions={
          <button className="btn btn--primary" onClick={optimize} disabled={loading}>
            {loading ? "Optimizing…" : "Optimize"}
          </button>
        }
      />

      <Card title="Requirement">
        <div className="opt-req">
          <FormField label="Required tonnes" type="number" value={requiredTonnes} onChange={setRequiredTonnes} />
          <FormField label="Tolerance (%)" type="number" value={tolerance} onChange={setTolerance} />
        </div>
      </Card>

      <Card
        title="Candidate voyages"
        subtitle="Each is an origin × vessel-type × contract option the solver may select"
        actions={<button className="btn" onClick={addCandidate}>Add candidate</button>}
        padded={false}
      >
        <div className="opt-candidates">
          <div className="opt-candidates__head">
            <span>ID</span><span>Origin</span><span>Type</span><span>Contract</span>
            <span>Cost/voyage</span><span>Capacity (t)</span><span>Max</span><span></span>
          </div>
          {candidates.map((c, idx) => (
            <div className="opt-candidates__row" key={idx}>
              <input className="ui-field__input" value={c.id} onChange={(e) => updateCandidate(idx, "id", e.target.value)} />
              <input className="ui-field__input" value={c.origin} onChange={(e) => updateCandidate(idx, "origin", e.target.value)} />
              <input className="ui-field__input" value={c.vessel_type} onChange={(e) => updateCandidate(idx, "vessel_type", e.target.value)} />
              <input className="ui-field__input" value={c.contract_strategy} onChange={(e) => updateCandidate(idx, "contract_strategy", e.target.value)} />
              <input className="ui-field__input" type="number" value={String(c.cost_per_voyage)} onChange={(e) => updateCandidate(idx, "cost_per_voyage", e.target.value)} />
              <input className="ui-field__input" type="number" value={String(c.capacity_tonnes)} onChange={(e) => updateCandidate(idx, "capacity_tonnes", e.target.value)} />
              <input className="ui-field__input" type="number" value={String(c.max_voyages)} onChange={(e) => updateCandidate(idx, "max_voyages", e.target.value)} />
              <button className="btn" onClick={() => removeCandidate(idx)} aria-label="Remove">✕</button>
            </div>
          ))}
        </div>
      </Card>

      {loading ? (
        <Card><Loading fill label="Solving…" /></Card>
      ) : error ? (
        <Card><ErrorState onRetry={optimize} message={error.displayMessage} /></Card>
      ) : result ? (
        <div className="opt-results">
          <div className="opt-stats">
            <StatTile label="Status" value={humanize(result.status)} />
            <StatTile label="Total cost" value={formatCurrency(result.total_cost, result.currency)} />
            <StatTile label="Total tonnes" value={formatCurrency(result.total_tonnes, "").trim()} />
            <StatTile label="Estimated savings" value={formatCurrency(result.estimated_savings, result.currency)} note="vs single-source baseline" />
          </div>
          <Card title="Selected voyages" padded={false}>
            <Table columns={selectedColumns} rows={result.selected_voyages} rowKey={(r) => r.candidate_id} />
          </Card>
          <Card title="Allocation">
            <div className="opt-alloc">
              <div>
                <h4>By origin</h4>
                <ul>{Object.entries(result.origin_allocation).map(([k, v]) => <li key={k}>{k}: {formatCurrency(v, "").trim()} t</li>)}</ul>
              </div>
              <div>
                <h4>By vessel type</h4>
                <ul>{Object.entries(result.vessel_type_allocation).map(([k, v]) => <li key={k}>{humanize(k)}: {formatCurrency(v, "").trim()} t</li>)}</ul>
              </div>
              <div>
                <h4>Contract mix</h4>
                <ul>{Object.entries(result.contract_strategy_mix).map(([k, v]) => <li key={k}>{humanize(k)}: {v} voyage(s)</li>)}</ul>
              </div>
            </div>
          </Card>
          {result.notes.length > 0 && <p className="opt-note">{result.notes.join(" ")}</p>}
        </div>
      ) : null}
    </>
  );
}
