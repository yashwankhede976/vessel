import { useState } from "react";
import PageHeader from "../components/layout/PageHeader";
import { Badge, Card, FormField, Modal, Table } from "../components/ui";
import type { BadgeVariant, Column } from "../components/ui";
import { api, useApi } from "../api";
import type { Vessel } from "../api";
import { formatNumber, humanize } from "../lib/format";
import "./VesselsPage.css";

/**
 * Vessel Intelligence: filterable vessel table (identity, dimensions, position,
 * availability) backed by the live vessels API, with a detail modal. All fields
 * are REAL catalogue/AIS data served by the backend.
 */
const VESSEL_TYPES = ["handysize", "supramax", "ultramax", "panamax", "kamsarmax", "post_panamax", "capesize", "other"];
const AVAILABILITY = ["open", "laden", "ballast", "fixed", "unknown"];

const availabilityVariant = (s: string): BadgeVariant =>
  s === "open" ? "success" : s === "fixed" ? "danger" : s === "laden" ? "warning" : "neutral";

export default function VesselsPage() {
  const [vesselType, setVesselType] = useState("");
  const [availability, setAvailability] = useState("");
  const [dwtMin, setDwtMin] = useState("");
  const [dwtMax, setDwtMax] = useState("");
  const [selected, setSelected] = useState<Vessel | null>(null);

  const state = useApi(
    (signal) =>
      api.vessels.list(
        {
          vessel_type: vesselType || undefined,
          availability_status: availability || undefined,
          dwt_min: dwtMin ? Number(dwtMin) : undefined,
          dwt_max: dwtMax ? Number(dwtMax) : undefined,
          page_size: 100,
        },
        signal,
      ),
    [vesselType, availability, dwtMin, dwtMax],
  );

  const vessels = state.data?.items ?? [];

  const columns: Column<Vessel>[] = [
    { key: "name", header: "Vessel", render: (v) => (
      <button className="vessels__name" onClick={() => setSelected(v)}>{v.name}</button>
    ) },
    { key: "vessel_type_display", header: "Type" },
    { key: "dwt", header: "DWT (t)", align: "right", render: (v) => formatNumber(v.dwt, 0) },
    { key: "draft", header: "Draft (m)", align: "right", render: (v) => formatNumber(v.draft) },
    { key: "loa", header: "LOA (m)", align: "right", render: (v) => formatNumber(v.loa) },
    {
      key: "speed",
      header: "Speed (kn)",
      align: "right",
      render: (v) => (v.latest_position?.sog ? formatNumber(v.latest_position.sog) : v.speed ? formatNumber(v.speed) : "—"),
    },
    {
      key: "availability_status",
      header: "Availability",
      render: (v) => <Badge variant={availabilityVariant(v.availability_status)}>{humanize(v.availability_status)}</Badge>,
    },
    {
      key: "position",
      header: "Position",
      render: (v) =>
        v.latest_position
          ? `${formatNumber(v.latest_position.latitude)}, ${formatNumber(v.latest_position.longitude)}`
          : "—",
    },
  ];

  return (
    <>
      <PageHeader
        title="Vessel Intelligence"
        description="Dry-bulk tonnage with identity, dimensions, latest position and availability. Click a vessel for full specifications."
      />

      <Card title="Filters">
        <div className="vessels-filters">
          <FormField label="Vessel type">
            {(id) => (
              <select id={id} className="ui-field__input" value={vesselType} onChange={(e) => setVesselType(e.target.value)}>
                <option value="">All types</option>
                {VESSEL_TYPES.map((t) => <option key={t} value={t}>{humanize(t)}</option>)}
              </select>
            )}
          </FormField>
          <FormField label="Availability">
            {(id) => (
              <select id={id} className="ui-field__input" value={availability} onChange={(e) => setAvailability(e.target.value)}>
                <option value="">All statuses</option>
                {AVAILABILITY.map((a) => <option key={a} value={a}>{humanize(a)}</option>)}
              </select>
            )}
          </FormField>
          <FormField label="DWT min" type="number" value={dwtMin} onChange={setDwtMin} />
          <FormField label="DWT max" type="number" value={dwtMax} onChange={setDwtMax} />
        </div>
      </Card>

      <Card title={`Vessels (${vessels.length})`} padded={false}>
        <Table
          columns={columns}
          rows={vessels}
          rowKey={(v) => v.id}
          loading={state.loading}
          error={!!state.error}
          onRetry={state.refetch}
          emptyMessage="No vessels match these filters."
        />
      </Card>

      <Modal
        open={selected !== null}
        onClose={() => setSelected(null)}
        title={selected?.name ?? "Vessel"}
        size="md"
      >
        {selected && (
          <dl className="vessels-detail">
            {[
              ["IMO", selected.imo],
              ["MMSI", selected.mmsi ?? "—"],
              ["Type", selected.vessel_type_display],
              ["DWT (t)", formatNumber(selected.dwt, 0)],
              ["LOA (m)", formatNumber(selected.loa)],
              ["Beam (m)", formatNumber(selected.beam)],
              ["Draft (m)", formatNumber(selected.draft)],
              ["Flag", selected.flag || "—"],
              ["Year built", selected.year_built ?? "—"],
              ["Service speed (kn)", selected.speed ? formatNumber(selected.speed) : "—"],
              ["Availability", selected.availability_status_display],
              ["Open date", selected.open_date ?? "—"],
            ].map(([label, value]) => (
              <div key={String(label)} className="vessels-detail__row">
                <dt>{label}</dt>
                <dd>{value}</dd>
              </div>
            ))}
            {selected.latest_position && (
              <div className="vessels-detail__row">
                <dt>Latest position</dt>
                <dd>
                  {formatNumber(selected.latest_position.latitude)},{" "}
                  {formatNumber(selected.latest_position.longitude)} ·{" "}
                  {new Date(selected.latest_position.timestamp).toLocaleString()}
                </dd>
              </div>
            )}
          </dl>
        )}
      </Modal>
    </>
  );
}
