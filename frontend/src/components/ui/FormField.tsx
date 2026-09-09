import { useId } from "react";
import type { ReactNode } from "react";
import "./FormField.css";

interface BaseProps {
  label: string;
  hint?: ReactNode;
  error?: ReactNode;
  required?: boolean;
}

interface FormFieldProps extends BaseProps {
  /** Render a custom control; receives the id to wire the label. */
  children?: (id: string) => ReactNode;
  /** Convenience: render a simple text-like input when no children given. */
  type?: string;
  placeholder?: string;
  value?: string;
  onChange?: (value: string) => void;
  name?: string;
}

/** A labelled form control wrapper with hint and error text. */
export default function FormField({
  label,
  hint,
  error,
  required = false,
  children,
  type = "text",
  placeholder,
  value,
  onChange,
  name,
}: FormFieldProps) {
  const id = useId();
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined;

  return (
    <div className={error ? "ui-field ui-field--error" : "ui-field"}>
      <label className="ui-field__label" htmlFor={id}>
        {label}
        {required && <span className="ui-field__required" aria-hidden="true"> *</span>}
      </label>

      {children ? (
        children(id)
      ) : (
        <input
          id={id}
          name={name}
          className="ui-field__input"
          type={type}
          placeholder={placeholder}
          value={value}
          required={required}
          aria-describedby={describedBy}
          aria-invalid={Boolean(error)}
          onChange={(e) => onChange?.(e.target.value)}
        />
      )}

      {hint && !error && (
        <p id={`${id}-hint`} className="ui-field__hint">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} className="ui-field__error">
          {error}
        </p>
      )}
    </div>
  );
}
