import type { ReactNode } from "react";
import "./EmptyState.css";

interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  message?: ReactNode;
  action?: ReactNode;
  /** Compact variant for use inside small cards. */
  compact?: boolean;
}

/**
 * Professional empty state. Used wherever a data-driven region has nothing to
 * show yet (common before the datasets are seeded), instead of a bare "No data".
 */
export default function EmptyState({ icon, title, message, action, compact }: EmptyStateProps) {
  return (
    <div className={compact ? "empty-state empty-state--compact" : "empty-state"}>
      {icon && <div className="empty-state__icon" aria-hidden="true">{icon}</div>}
      <p className="empty-state__title">{title}</p>
      {message && <p className="empty-state__message">{message}</p>}
      {action && <div className="empty-state__action">{action}</div>}
    </div>
  );
}
