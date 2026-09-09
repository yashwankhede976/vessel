import type { ReactNode } from "react";
import "./Card.css";

interface CardProps {
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  footer?: ReactNode;
  children?: ReactNode;
  className?: string;
  padded?: boolean;
}

/** A surface container for grouping related content. */
export default function Card({
  title,
  subtitle,
  actions,
  footer,
  children,
  className = "",
  padded = true,
}: CardProps) {
  const hasHeader = title || subtitle || actions;
  return (
    <section className={`ui-card ${className}`}>
      {hasHeader && (
        <header className="ui-card__header">
          <div>
            {title && <h3 className="ui-card__title">{title}</h3>}
            {subtitle && <p className="ui-card__subtitle">{subtitle}</p>}
          </div>
          {actions && <div className="ui-card__actions">{actions}</div>}
        </header>
      )}
      <div className={padded ? "ui-card__body" : "ui-card__body ui-card__body--flush"}>
        {children}
      </div>
      {footer && <footer className="ui-card__footer">{footer}</footer>}
    </section>
  );
}
