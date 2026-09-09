import "./Loading.css";

interface LoadingProps {
  label?: string;
  /** When true, fills its container and centers vertically. */
  fill?: boolean;
}

/** A spinner + label used for pending/loading states. */
export default function Loading({ label = "Loading…", fill = false }: LoadingProps) {
  return (
    <div className={fill ? "ui-loading ui-loading--fill" : "ui-loading"} role="status">
      <span className="ui-loading__spinner" aria-hidden="true" />
      <span className="ui-loading__label">{label}</span>
    </div>
  );
}
