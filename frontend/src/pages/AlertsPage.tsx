import { useMemo, useState } from "react";
import PageHeader from "../components/layout/PageHeader";
import { Badge, Card, FormField, Table } from "../components/ui";
import type { BadgeVariant, Column } from "../components/ui";
import { api, useApi, ApiError } from "../api";
import type { DecisionAlert } from "../api";
import { humanize } from "../lib/format";
import "./AlertsPage.css";

/**
 * Alert Center: lists alerts from the real /alerts/ ViewSet with severity/time/
 * entity/trigger/message/recommended action, status/type/severity filters,
 * client-side search, and acknowledge/resolve actions.
 */
const SEVERITY_VARIANT: Record<string, BadgeVariant> = {
  critical: "danger",
  high: "danger",
  medium: "warning",
  low: "info",
  info: "neutral",
};
const STATUS_VARIANT: Record<string, BadgeVariant> = {
  new: "danger",
  acknowledged: "warning",
  resolved: "success",
};

export default function AlertsPage() {
  const [status, setStatus] = useState("");
  const [severity, setSeverity] = useState("");
  const [search, setSearch] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const state = useApi(
    (signal) =>
      api.alerts.list(
        {
          status: (status || undefined) as "new" | "acknowledged" | "resolved" | undefined,
          severity: severity || undefined,
          page_size: 100,
        },
        signal,
      ),
    [status, severity],
  );

  const alerts = state.data?.items ?? [];
  const filtered = useMemo(() => {
    if (!search.trim()) return alerts;
    const q = search.toLowerCase();
    return alerts.filter(
      (a) =>
        a.message.toLowerCase().includes(q) ||
        a.entity.toLowerCase().includes(q) ||
        a.alert_type.toLowerCase().includes(q),
    );
  }, [alerts, search]);

  const act = async (id: number, action: "acknowledge" | "resolve") => {
    setBusyId(id);
    setActionError(null);
    try {
      if (action === "acknowledge") await api.alerts.acknowledge(id);
      else await api.alerts.resolve(id);
      state.refetch();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.displayMessage : "Action failed.");
    } finally {
      setBusyId(null);
    }
  };

  const columns: Column<DecisionAlert>[] = [
    {
      key: "severity",
      header: "Severity",
      render: (a) => <Badge variant={SEVERITY_VARIANT[a.severity] ?? "neutral"}>{humanize(a.severity)}</Badge>,
    },
    { key: "timestamp", header: "Time", render: (a) => new Date(a.timestamp).toLocaleString() },
    { key: "alert_type", header: "Type", render: (a) => humanize(a.alert_type) },
    { key: "entity", header: "Entity" },
    { key: "message", header: "Message" },
    { key: "recommended_action", header: "Recommended action", render: (a) => a.recommended_action || "—" },
    {
      key: "status",
      header: "Status",
      render: (a) => <Badge variant={STATUS_VARIANT[a.status] ?? "neutral"}>{humanize(a.status)}</Badge>,
    },
    {
      key: "actions",
      header: "",
      render: (a) => (
        <div className="alerts__actions">
          {a.status !== "acknowledged" && a.status !== "resolved" && (
            <button className="btn" disabled={busyId === a.id} onClick={() => act(a.id, "acknowledge")}>
              Ack
            </button>
          )}
          {a.status !== "resolved" && (
            <button className="btn" disabled={busyId === a.id} onClick={() => act(a.id, "resolve")}>
              Resolve
            </button>
          )}
        </div>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Alert Center"
        description="Material events — freight moves, congestion, cyclone/marine warnings, vessel scarcity, ETA delay, port incompatibility, unusual market pressure — with recommended actions."
      />

      <Card title="Filters">
        <div className="alerts-filters">
          <FormField label="Status">
            {(id) => (
              <select id={id} className="ui-field__input" value={status} onChange={(e) => setStatus(e.target.value)}>
                <option value="">All</option>
                <option value="new">New</option>
                <option value="acknowledged">Acknowledged</option>
                <option value="resolved">Resolved</option>
              </select>
            )}
          </FormField>
          <FormField label="Severity">
            {(id) => (
              <select id={id} className="ui-field__input" value={severity} onChange={(e) => setSeverity(e.target.value)}>
                <option value="">All</option>
                {["critical", "high", "medium", "low", "info"].map((s) => (
                  <option key={s} value={s}>{humanize(s)}</option>
                ))}
              </select>
            )}
          </FormField>
          <FormField label="Search" placeholder="message, entity, type…" value={search} onChange={setSearch} />
        </div>
        {actionError && <p className="alerts-error">{actionError}</p>}
      </Card>

      <Card title={`Alerts (${filtered.length})`} padded={false}>
        <Table
          columns={columns}
          rows={filtered}
          rowKey={(a) => a.id}
          loading={state.loading}
          error={!!state.error}
          onRetry={state.refetch}
          emptyMessage="No alerts match these filters."
        />
      </Card>
    </>
  );
}
