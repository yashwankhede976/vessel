import { useEffect, useState } from "react";
import PageHeader from "../../components/layout/PageHeader";
import { Card, ErrorState, Loading } from "../../components/ui";
import { api, useApi } from "../../api";
import EastCoastMap from "./EastCoastMap";
import PortCard from "./PortCard";
import PortDetailPanel from "./PortDetailPanel";
import CompatibilityTester from "./CompatibilityTester";
import "./PortsPage.css";

/**
 * Port Intelligence page: East Coast locator map, port cards, port/berth detail
 * with source information, and a vessel compatibility tester. No live congestion
 * data (out of scope for this task).
 */
export default function PortsPage() {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [compatibleBerthIds, setCompatibleBerthIds] = useState<Set<number>>(new Set());

  // Port list (East Coast India).
  const listState = useApi(
    (signal) => api.ports.list({ coast: "east_coast_india", page_size: 50 }, signal),
    [],
  );
  const ports = listState.data?.items ?? [];

  // Auto-select the first port once loaded.
  useEffect(() => {
    if (selectedId === null && ports.length > 0) {
      setSelectedId(ports[0].id);
    }
  }, [ports, selectedId]);

  // Selected port detail (with berths + metadata).
  const detailState = useApi(
    (signal) =>
      selectedId ? api.ports.retrieve(selectedId, signal) : Promise.resolve(null),
    [selectedId],
  );

  const handleSelect = (id: number) => {
    setSelectedId(id);
    setCompatibleBerthIds(new Set()); // clear prior tester highlights
  };

  return (
    <>
      <PageHeader
        title="Port Intelligence"
        description="East Coast India ports: berths, physical and operational constraints, and sourced references. Congestion data is not included here."
      />

      <div className="ports-layout">
        <aside className="ports-layout__left">
          <EastCoastMap ports={ports} selectedId={selectedId} onSelect={handleSelect} />

          <Card title="Ports" padded={false}>
            <div className="ports-list">
              {listState.loading ? (
                <Loading fill label="Loading ports…" />
              ) : listState.error ? (
                <ErrorState onRetry={listState.refetch} message={listState.error.displayMessage} />
              ) : ports.length === 0 ? (
                <p className="pd__muted" style={{ padding: "var(--sp-4)" }}>
                  No ports found.
                </p>
              ) : (
                ports.map((port) => (
                  <PortCard
                    key={port.id}
                    port={port}
                    selected={port.id === selectedId}
                    onSelect={handleSelect}
                  />
                ))
              )}
            </div>
          </Card>
        </aside>

        <div className="ports-layout__main">
          <PortDetailPanel
            port={detailState.data}
            loading={detailState.loading}
            error={detailState.error}
            onRetry={detailState.refetch}
            compatibleBerthIds={compatibleBerthIds}
          />
          <CompatibilityTester
            port={detailState.data}
            onResults={setCompatibleBerthIds}
          />
        </div>
      </div>
    </>
  );
}
