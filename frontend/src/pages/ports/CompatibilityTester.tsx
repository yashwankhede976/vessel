import { useMemo, useState } from "react";
import { Badge, Card, FormField } from "../../components/ui";
import { api, useApi } from "../../api";
import type { PortDetail, Vessel } from "../../api";
import { evaluateBerth } from "./compatibility";
import type { BerthCompatResult, CompatStatus, VesselSpec } from "./compatibility";
import "./CompatibilityTester.css";

interface CompatibilityTesterProps {
  /** The currently selected destination port (with berths). */
  port: PortDetail | null;
  /** Report compatible berth ids up to the parent for map/table highlighting. */
  onResults?: (compatibleBerthIds: Set<number>) => void;
}

// Illustrative origins (overseas load regions) — informational context only.
const ORIGINS = ["Australia", "Indonesia", "Mozambique", "USA", "Russia"];

const VESSEL_TYPES: { value: string; label: string }[] = [
  { value: "handysize", label: "Handysize" },
  { value: "supramax", label: "Supramax" },
  { value: "panamax", label: "Panamax" },
  { value: "capesize", label: "Capesize" },
];

const statusVariant: Record<CompatStatus, "success" | "warning" | "danger" | "neutral"> = {
  COMPATIBLE: "success",
  CONDITIONAL: "warning",
  UNKNOWN: "neutral",
  INCOMPATIBLE: "danger",
};

export default function CompatibilityTester({ port, onResults }: CompatibilityTesterProps) {
  const [origin, setOrigin] = useState<string>(ORIGINS[0]);
  const [vesselType, setVesselType] = useState<string>("panamax");
  const [vesselId, setVesselId] = useState<string>("");
  const [cargo, setCargo] = useState<string>("Thermal Coal");
  const [results, setResults] = useState<BerthCompatResult[] | null>(null);

  // Load vessels of the chosen type for the vessel selector.
  const vesselsState = useApi(
    (signal) => api.vessels.list({ vessel_type: vesselType, page_size: 100 }, signal),
    [vesselType],
  );
  const vessels: Vessel[] = vesselsState.data?.items ?? [];

  const selectedVessel = useMemo(
    () => vessels.find((v) => String(v.id) === vesselId) ?? null,
    [vessels, vesselId],
  );

  const canRun = Boolean(port && selectedVessel);

  const run = () => {
    if (!port || !selectedVessel) return;
    const spec: VesselSpec = {
      loa: Number(selectedVessel.loa),
      beam: Number(selectedVessel.beam),
      draft: Number(selectedVessel.draft),
      cargo: cargo || undefined,
    };
    const evaluated = port.berths.map((b) => evaluateBerth(spec, b));
    setResults(evaluated);
    const compatibleIds = new Set(
      evaluated.filter((r) => r.status === "COMPATIBLE").map((r) => r.berthId),
    );
    onResults?.(compatibleIds);
  };

  const berthName = (id: number) => port?.berths.find((b) => b.id === id)?.berth_name ?? "";

  return (
    <Card title="Vessel compatibility tester" subtitle="Uses published berth limits — no live data">
      <div className="ct__form">
        <FormField label="Origin">
          {(id) => (
            <select id={id} value={origin} onChange={(e) => setOrigin(e.target.value)}>
              {ORIGINS.map((o) => (
                <option key={o} value={o}>
                  {o}
                </option>
              ))}
            </select>
          )}
        </FormField>

        <FormField label="Destination">
          {(id) => (
            <input id={id} value={port ? port.name : "Select a port"} readOnly />
          )}
        </FormField>

        <FormField label="Vessel type">
          {(id) => (
            <select
              id={id}
              value={vesselType}
              onChange={(e) => {
                setVesselType(e.target.value);
                setVesselId("");
              }}
            >
              {VESSEL_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          )}
        </FormField>

        <FormField
          label="Vessel"
          hint={vesselsState.loading ? "Loading vessels…" : `${vessels.length} available`}
        >
          {(id) => (
            <select id={id} value={vesselId} onChange={(e) => setVesselId(e.target.value)}>
              <option value="">Select a vessel</option>
              {vessels.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name} · {v.dwt}t
                </option>
              ))}
            </select>
          )}
        </FormField>

        <FormField label="Intended cargo">
          {(id) => (
            <input id={id} value={cargo} onChange={(e) => setCargo(e.target.value)} />
          )}
        </FormField>
      </div>

      <div className="ct__actions">
        <button className="btn btn--primary" disabled={!canRun} onClick={run}>
          Check compatible berths
        </button>
        {!port && <span className="ct__hint">Select a destination port first.</span>}
        {port && !selectedVessel && <span className="ct__hint">Select a vessel to test.</span>}
      </div>

      {results && (
        <div className="ct__results">
          <p className="ct__origin-note">
            {origin} → {port?.name} · {selectedVessel?.name}
          </p>
          {results.length === 0 ? (
            <p className="pd__muted">This port has no berths with published dimensions to test.</p>
          ) : (
            <ul className="ct__list">
              {results.map((r) => (
                <li key={r.berthId} className="ct__item">
                  <div className="ct__item-head">
                    <span className="ct__berth">{berthName(r.berthId)}</span>
                    <Badge variant={statusVariant[r.status]} dot>
                      {r.status}
                    </Badge>
                  </div>
                  {r.reasons.length > 0 && (
                    <ul className="ct__reasons">
                      {r.reasons.map((reason) => (
                        <li key={reason}>{reason}</li>
                      ))}
                    </ul>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </Card>
  );
}
