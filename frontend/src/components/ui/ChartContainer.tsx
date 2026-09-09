import type { ReactNode } from "react";
import Loading from "./Loading";
import ErrorState from "./ErrorState";
import "./ChartContainer.css";

interface ChartContainerProps {
  title?: ReactNode;
  actions?: ReactNode;
  height?: number;
  loading?: boolean;
  error?: boolean;
  onRetry?: () => void;
  children?: ReactNode;
  /** Shown when there are no children and not loading/error. */
  placeholder?: ReactNode;
}

/**
 * A framed area for a chart. The actual charting library plugs in as children
 * later; for now it renders a placeholder so layouts are complete.
 */
export default function ChartContainer({
  title,
  actions,
  height = 280,
  loading = false,
  error = false,
  onRetry,
  children,
  placeholder = "Chart will render here",
}: ChartContainerProps) {
  return (
    <div className="ui-chart">
      {(title || actions) && (
        <div className="ui-chart__header">
          {title && <h3 className="ui-chart__title">{title}</h3>}
          {actions && <div className="ui-chart__actions">{actions}</div>}
        </div>
      )}
      <div className="ui-chart__body" style={{ height }}>
        {loading ? (
          <Loading fill label="Loading chart…" />
        ) : error ? (
          <ErrorState onRetry={onRetry} message="The chart data could not be loaded." />
        ) : children ? (
          children
        ) : (
          <div className="ui-chart__placeholder">{placeholder}</div>
        )}
      </div>
    </div>
  );
}
