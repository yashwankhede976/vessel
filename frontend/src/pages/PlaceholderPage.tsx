import type { ReactNode } from "react";
import PageHeader from "../components/layout/PageHeader";
import { Card } from "../components/ui";

interface PlaceholderPageProps {
  title: string;
  description: ReactNode;
  /** Short bullet list of what will live here (no data yet). */
  planned?: string[];
}

/**
 * A consistent "coming soon" page used for routes whose data/features are not
 * implemented yet. Keeps the shell navigable without mocking API data.
 */
export default function PlaceholderPage({
  title,
  description,
  planned = [],
}: PlaceholderPageProps) {
  return (
    <>
      <PageHeader title={title} description={description} />
      <Card title="Planned for this section">
        {planned.length > 0 ? (
          <ul style={{ margin: 0, paddingLeft: "1.1rem", color: "var(--color-text-muted)" }}>
            {planned.map((item) => (
              <li key={item} style={{ marginBottom: "6px" }}>
                {item}
              </li>
            ))}
          </ul>
        ) : (
          <p style={{ margin: 0, color: "var(--color-text-muted)" }}>
            This section is part of the application shell. Functionality will be
            added in a later task.
          </p>
        )}
      </Card>
    </>
  );
}
