import { Badge, Card, ErrorState, Loading, Table } from "../../components/ui";
import type { Column } from "../../components/ui";
import type { ApiError, Berth, PortDetail } from "../../api";
import { measure, metaSource, metaValue } from "./format";
import "./PortDetailPanel.css";

interface PortDetailPanelProps {
  port: PortDetail | null;
  loading: boolean;
  error: ApiError | null;
  onRetry: () => void;
  /** Berth ids highlighted as compatible by the tester (optional). */
  compatibleBerthIds?: Set<number>;
}

function commodityBadges(names: string[]) {
  if (names.length === 0) return <span className="pd__muted">Not documented</span>;
  return (
    <span className="pd__commodities">
      {names.map((n) => (
        <Badge key={n} variant="info">
          {n}
        </Badge>
      ))}
    </span>
  );
}

export default function PortDetailPanel({
  port,
  loading,
  error,
  onRetry,
  compatibleBerthIds,
}: PortDetailPanelProps) {
  if (loading) return <Loading fill label="Loading port details…" />;
  if (error) return <ErrorState onRetry={onRetry} message={error.displayMessage} />;
  if (!port) {
    return (
      <Card>
        <p className="pd__muted" style={{ margin: 0 }}>
          Select a port to view its berths, constraints, and sources.
        </p>
      </Card>
    );
  }

  const meta = port.metadata;

  // Port-level facts with provenance (each is a sourced field or UNKNOWN).
  const facts: { label: string; key: string }[] = [
    { label: "Max LOA", key: "max_loa_m" },
    { label: "Max beam", key: "max_beam_m" },
    { label: "Max draft", key: "max_draft_m" },
    { label: "Max DWT", key: "max_dwt_t" },
    { label: "Handling", key: "handling_rate_tpd" },
    { label: "Cargo types", key: "cargo_types" },
    { label: "Operational restrictions", key: "operational_constraints" },
    { label: "Handling capabilities", key: "handling_capabilities" },
  ];

  const berthColumns: Column<Berth>[] = [
    {
      key: "berth_name",
      header: "Berth",
      render: (b) => (
        <span>
          {b.berth_name}
          {compatibleBerthIds?.has(b.id) && (
            <Badge variant="success" className="pd__berth-flag">
              Compatible
            </Badge>
          )}
        </span>
      ),
    },
    { key: "max_loa", header: "LOA", align: "right", render: (b) => measure(b.max_loa, "m") },
    { key: "max_beam", header: "Beam", align: "right", render: (b) => measure(b.max_beam, "m") },
    { key: "max_draft", header: "Draft", align: "right", render: (b) => measure(b.max_draft, "m") },
    {
      key: "handling_rate",
      header: "Handling",
      align: "right",
      render: (b) =>
        Number(b.handling_rate) > 0 ? measure(b.handling_rate, "t/day") : "UNKNOWN",
    },
    {
      key: "supported_commodities",
      header: "Commodities",
      render: (b) => commodityBadges(b.supported_commodities),
    },
  ];

  return (
    <div className="pd">
      <Card
        title={port.name}
        subtitle={`${port.coast_display} · ${port.port_type_display}${
          port.unlocode ? ` · ${port.unlocode}` : ""
        }`}
      >
        <dl className="pd__facts">
          {facts.map(({ label, key }) => {
            const value = metaValue(meta, key);
            const src = metaSource(meta, key);
            return (
              <div className="pd__fact" key={key}>
                <dt>{label}</dt>
                <dd>
                  <span className={value === "UNKNOWN" ? "pd__unknown" : ""}>{value}</span>
                  {src && (
                    <span
                      className="pd__source"
                      title={`${src.source} (as of ${src.source_date})`}
                    >
                      source: {src.source} · {src.source_date}
                    </span>
                  )}
                </dd>
              </div>
            );
          })}
        </dl>
      </Card>

      <Card title="Berths" subtitle="Published limits only — UNKNOWN where not officially documented" padded={false}>
        <Table
          columns={berthColumns}
          rows={port.berths}
          rowKey={(b) => b.id}
          emptyMessage="No berths with published dimensions for this port."
        />
      </Card>
    </div>
  );
}
