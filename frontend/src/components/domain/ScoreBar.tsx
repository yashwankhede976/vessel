import "./ScoreBar.css";

/**
 * A horizontal 0..1 (or 0..100) contribution bar for factor breakdowns (risk,
 * market pressure, suitability). Pure CSS width; no chart library. An UNKNOWN
 * factor renders a muted "UNKNOWN" marker instead of a bar (never a fake value).
 */
export default function ScoreBar({
  label,
  value,
  max = 1,
  unknown = false,
  note,
  tone = "accent",
}: {
  label: string;
  value?: number | null;
  max?: number;
  unknown?: boolean;
  note?: string;
  tone?: "accent" | "danger" | "warning" | "success" | "info";
}) {
  const pct =
    !unknown && value != null && max > 0
      ? Math.max(0, Math.min(100, (value / max) * 100))
      : 0;
  return (
    <div className="score-bar">
      <div className="score-bar__row">
        <span className="score-bar__label">{label}</span>
        <span className="score-bar__value">
          {unknown || value == null ? (
            <span className="score-bar__unknown">UNKNOWN</span>
          ) : (
            (max === 1 ? value.toFixed(2) : Math.round(value).toString())
          )}
        </span>
      </div>
      <div className="score-bar__track" aria-hidden={unknown}>
        {!unknown && (
          <div
            className={`score-bar__fill score-bar__fill--${tone}`}
            style={{ width: `${pct}%` }}
          />
        )}
      </div>
      {note && <p className="score-bar__note">{note}</p>}
    </div>
  );
}
