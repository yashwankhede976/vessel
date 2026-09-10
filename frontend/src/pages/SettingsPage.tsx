import PageHeader from "../components/layout/PageHeader";
import { Badge, Card, ErrorState, Loading, Table } from "../components/ui";
import type { BadgeVariant, Column } from "../components/ui";
import { api, useApi } from "../api";
import type { ExternalServiceHealth } from "../api";
import "./SettingsPage.css";

/**
 * Settings: application preferences plus a live view of external-service health
 * from GET /system/external-services/. The health endpoint never returns API
 * keys — only a `configured` boolean — so nothing sensitive is shown.
 */
export default function SettingsPage() {
  const health = useApi((signal) => api.system.externalServices(signal), []);
  const services = health.data?.services ?? [];

  const columns: Column<ExternalServiceHealth>[] = [
    { key: "provider", header: "Provider", render: (s) => s.provider },
    {
      key: "configured",
      header: "Configured",
      render: (s) => <Badge variant={s.configured ? "success" : "neutral"}>{s.configured ? "Yes" : "No"}</Badge>,
    },
    {
      key: "needs_key",
      header: "Credential",
      render: (s) => (s.needs_key ? <Badge variant="warning">Key required</Badge> : <Badge variant="success">Keyless</Badge>),
    },
    { key: "last_success", header: "Last success", render: (s) => (s.last_success ? new Date(s.last_success).toLocaleString() : "—") },
    { key: "last_failure", header: "Last failure", render: (s) => (s.last_failure ? new Date(s.last_failure).toLocaleString() : "—") },
    {
      key: "freshness",
      header: "Freshness",
      render: (s) => {
        const worst = s.data_freshness[0];
        const variant: BadgeVariant = worst?.level === "FRESH" ? "success" : worst?.level === "STALE" ? "warning" : worst?.level === "VERY_STALE" ? "danger" : "neutral";
        return worst ? <Badge variant={variant}>{worst.level}</Badge> : "—";
      },
    },
  ];

  return (
    <>
      <PageHeader
        title="Settings"
        description="Application preferences and the status of external data providers. API keys are held on the backend and are never exposed here."
      />

      <Card title="Preferences" subtitle="Display defaults">
        <dl className="settings-prefs">
          <div><dt>Currency</dt><dd>USD (backend Decimal-precise)</dd></div>
          <div><dt>Units</dt><dd>Nautical miles · tonnes · knots</dd></div>
          <div><dt>Time zone</dt><dd>UTC (as served)</dd></div>
          <div><dt>Region focus</dt><dd>East Coast India · dry bulk</dd></div>
        </dl>
      </Card>

      <Card title="External data providers" subtitle="Configuration + health (no keys shown)" padded={false}>
        {health.loading ? (
          <Loading fill label="Checking providers…" />
        ) : health.error ? (
          <ErrorState onRetry={health.refetch} message={health.error.displayMessage} />
        ) : (
          <Table columns={columns} rows={services} rowKey={(s) => s.provider} emptyMessage="No providers reported." />
        )}
      </Card>
    </>
  );
}
