import type { ReactNode } from "react";
import { Card } from "../ui";
import "./StatTile.css";

/**
 * A compact KPI tile: label, big value, optional note and status/label slot.
 * Reuses Card so spacing/border/shadow match the rest of the system.
 */
export default function StatTile({
  label,
  value,
  note,
  badge,
}: {
  label: string;
  value: ReactNode;
  note?: ReactNode;
  badge?: ReactNode;
}) {
  return (
    <Card>
      <div className="stat-tile__top">
        <p className="stat-tile__label">{label}</p>
        {badge}
      </div>
      <p className="stat-tile__value">{value}</p>
      {note && <p className="stat-tile__note">{note}</p>}
    </Card>
  );
}
