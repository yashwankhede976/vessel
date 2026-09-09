import { Badge, Card } from "../../components/ui";
import type { Port } from "../../api";
import "./PortCard.css";

interface PortCardProps {
  port: Port;
  selected: boolean;
  onSelect: (id: number) => void;
}

/** A summary card for a single port in the list. */
export default function PortCard({ port, selected, onSelect }: PortCardProps) {
  return (
    <button
      type="button"
      className={selected ? "port-card port-card--selected" : "port-card"}
      onClick={() => onSelect(port.id)}
      aria-pressed={selected}
    >
      <Card>
        <div className="port-card__head">
          <div>
            <p className="port-card__name">{port.name}</p>
            <p className="port-card__sub">
              {port.unlocode ? `${port.unlocode} · ` : ""}
              {port.port_type_display}
            </p>
          </div>
          <Badge variant={selected ? "accent" : "neutral"}>
            {port.berth_count} {port.berth_count === 1 ? "berth" : "berths"}
          </Badge>
        </div>
        <p className="port-card__coords">
          {Number(port.latitude).toFixed(3)}, {Number(port.longitude).toFixed(3)}
        </p>
      </Card>
    </button>
  );
}
