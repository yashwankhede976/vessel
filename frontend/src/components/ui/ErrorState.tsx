import type { ReactNode } from "react";
import "./ErrorState.css";

interface ErrorStateProps {
  title?: string;
  message?: ReactNode;
  onRetry?: () => void;
  retryLabel?: string;
}

/** A non-blocking error panel with an optional retry action. */
export default function ErrorState({
  title = "Something went wrong",
  message = "The data could not be loaded.",
  onRetry,
  retryLabel = "Retry",
}: ErrorStateProps) {
  return (
    <div className="ui-error" role="alert">
      <div className="ui-error__icon" aria-hidden="true">
        !
      </div>
      <div className="ui-error__body">
        <p className="ui-error__title">{title}</p>
        <p className="ui-error__message">{message}</p>
      </div>
      {onRetry && (
        <button type="button" className="ui-error__retry" onClick={onRetry}>
          {retryLabel}
        </button>
      )}
    </div>
  );
}
