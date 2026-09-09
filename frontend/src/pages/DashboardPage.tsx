import { useState } from "react";
import PageHeader from "../components/layout/PageHeader";
import { Badge, Card, ChartContainer, Modal, Table } from "../components/ui";
import type { Column } from "../components/ui";
import "./DashboardPage.css";

// Static illustrative content only — no API data in this task.
interface LaneRow {
  id: number;
  lane: string;
  vesselType: string;
  rate: string;
  trend: "up" | "down" | "flat";
}

const LANE_ROWS: LaneRow[] = [
  { id: 1, lane: "Australia → Paradip", vesselType: "Capesize", rate: "—", trend: "up" },
  { id: 2, lane: "Indonesia → Visakhapatnam", vesselType: "Panamax", rate: "—", trend: "flat" },
  { id: 3, lane: "USA → Dhamra", vesselType: "Capesize", rate: "—", trend: "down" },
  { id: 4, lane: "Mozambique → Gangavaram", vesselType: "Supramax", rate: "—", trend: "up" },
];

const trendBadge = (trend: LaneRow["trend"]) => {
  if (trend === "up") return <Badge variant="danger" dot>Rising</Badge>;
  if (trend === "down") return <Badge variant="success" dot>Falling</Badge>;
  return <Badge variant="neutral" dot>Stable</Badge>;
};

const COLUMNS: Column<LaneRow>[] = [
  { key: "lane", header: "Lane" },
  { key: "vesselType", header: "Vessel class" },
  { key: "rate", header: "Rate / t", align: "right" },
  { key: "trend", header: "Forecast", render: (r) => trendBadge(r.trend) },
];

const KPIS = [
  { label: "Active lanes", value: "—", note: "origin → East Coast" },
  { label: "Open vessels", value: "—", note: "available now" },
  { label: "Avg. demurrage risk", value: "—", note: "across voyages" },
  { label: "Est. savings (30d)", value: "—", note: "vs baseline" },
];

export default function DashboardPage() {
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Overview of freight market, vessel availability, and decision signals for East Coast India dry-bulk procurement."
        actions={
          <button className="btn btn--primary" onClick={() => setModalOpen(true)}>
            New analysis
          </button>
        }
      />

      <div className="kpi-grid">
        {KPIS.map((kpi) => (
          <Card key={kpi.label}>
            <p className="kpi__label">{kpi.label}</p>
            <p className="kpi__value">{kpi.value}</p>
            <p className="kpi__note">{kpi.note}</p>
          </Card>
        ))}
      </div>

      <div className="dashboard-grid">
        <ChartContainer
          title="Freight rate forecast"
          height={320}
          placeholder="Freight forecast chart (data wired in a later task)"
        />
        <Card title="Market signals" subtitle="Illustrative only">
          <ul className="signal-list">
            <li>
              <Badge variant="warning" dot>Congestion</Badge>
              <span>Paradip waiting time elevated</span>
            </li>
            <li>
              <Badge variant="info" dot>Weather</Badge>
              <span>Bay of Bengal monsoon window</span>
            </li>
            <li>
              <Badge variant="accent" dot>Timing</Badge>
              <span>Short-term cover favoured on AU lane</span>
            </li>
          </ul>
        </Card>
      </div>

      <Card title="Key lanes" subtitle="Illustrative rows — no live data yet" padded={false}>
        <Table columns={COLUMNS} rows={LANE_ROWS} rowKey={(r) => r.id} />
      </Card>

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title="New analysis"
        footer={
          <>
            <button className="btn" onClick={() => setModalOpen(false)}>
              Cancel
            </button>
            <button className="btn btn--primary" onClick={() => setModalOpen(false)}>
              Continue
            </button>
          </>
        }
      >
        <p style={{ marginTop: 0, color: "var(--color-text-muted)" }}>
          This is a demonstration of the modal component. Analysis configuration
          will be implemented in a later task.
        </p>
      </Modal>
    </>
  );
}
