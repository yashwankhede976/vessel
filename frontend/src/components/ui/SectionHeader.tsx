import type { ReactNode } from "react";
import "./SectionHeader.css";

interface SectionHeaderProps {
  /** Small ordinal or kicker, e.g. "01" or "Overview". */
  eyebrow?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
}

/**
 * Editorial section divider used to group dashboard/page regions. Establishes
 * hierarchy through type + spacing rather than heavy chrome.
 */
export default function SectionHeader({ eyebrow, title, description, actions }: SectionHeaderProps) {
  return (
    <div className="section-header">
      <div className="section-header__text">
        {eyebrow && <span className="section-header__eyebrow">{eyebrow}</span>}
        <h2 className="section-header__title">{title}</h2>
        {description && <p className="section-header__desc">{description}</p>}
      </div>
      {actions && <div className="section-header__actions">{actions}</div>}
    </div>
  );
}
