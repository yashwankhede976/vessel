import { useState } from "react";
import { Badge } from "../ui";
import type { BadgeVariant } from "../ui";
import "./DecisionCard.css";

/**
 * The headline recommendation card. Highly visible: a large decision verb, the
 * lane/vessel context, expected saving, risk, and confidence, plus an
 * expandable "Why?" backed by actual backend factors (never invented copy).
 */
export interface DecisionFactor {
  label: string;
  value: string;
}

interface DecisionCardProps {
  decision: string; // e.g. FIX NOW / WAIT / PARTIAL FIX / MONITOR
  headline?: string; // e.g. "Panamax · Australia → Paradip"
  subline?: string; // e.g. "3-Voyage Contract"
  expectedSaving?: string;
  risk?: string; // LOW/MEDIUM/HIGH
  confidence?: number | null; // 0..1
  reason?: string;
  factors?: DecisionFactor[];
}

const decisionVariant = (decision: string): BadgeVariant => {
  const d = decision.toUpperCase();
  if (d.includes("FIX")) return "success";
  if (d.includes("WAIT")) return "warning";
  if (d.includes("MONITOR")) return "info";
  return "neutral";
};

const riskVariant = (risk?: string): BadgeVariant => {
  const r = (risk ?? "").toUpperCase();
  if (r === "HIGH" || r === "CRITICAL") return "danger";
  if (r === "MEDIUM") return "warning";
  if (r === "LOW") return "success";
  return "neutral";
};

export default function DecisionCard({
  decision,
  headline,
  subline,
  expectedSaving,
  risk,
  confidence,
  reason,
  factors = [],
}: DecisionCardProps) {
  const [showWhy, setShowWhy] = useState(false);

  return (
    <section className="decision-card" aria-label="Recommendation">
      <div className="decision-card__head">
        <p className="decision-card__eyebrow">Recommendation</p>
        <p className={`decision-card__verb decision-card__verb--${decisionVariant(decision)}`}>
          {decision}
        </p>
        {headline && <p className="decision-card__headline">{headline}</p>}
        {subline && <p className="decision-card__subline">{subline}</p>}
      </div>

      <div className="decision-card__metrics">
        {expectedSaving !== undefined && (
          <div className="decision-card__metric">
            <span className="decision-card__metric-label">Expected saving</span>
            <span className="decision-card__metric-value">{expectedSaving}</span>
          </div>
        )}
        <div className="decision-card__metric">
          <span className="decision-card__metric-label">Risk</span>
          <span className="decision-card__metric-value">
            <Badge variant={riskVariant(risk)}>{risk ?? "—"}</Badge>
          </span>
        </div>
        <div className="decision-card__metric">
          <span className="decision-card__metric-label">Confidence</span>
          <span className="decision-card__metric-value">
            {confidence != null ? `${Math.round(confidence * 100)}%` : "—"}
          </span>
        </div>
      </div>

      {(reason || factors.length > 0) && (
        <div className="decision-card__why">
          <button
            type="button"
            className="decision-card__why-toggle"
            aria-expanded={showWhy}
            onClick={() => setShowWhy((v) => !v)}
          >
            {showWhy ? "Hide reasoning" : "Why?"}
          </button>
          {showWhy && (
            <div className="decision-card__why-body">
              {reason && <p className="decision-card__reason">{reason}</p>}
              {factors.length > 0 && (
                <dl className="decision-card__factors">
                  {factors.map((f) => (
                    <div key={f.label} className="decision-card__factor">
                      <dt>{f.label}</dt>
                      <dd>{f.value}</dd>
                    </div>
                  ))}
                </dl>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
