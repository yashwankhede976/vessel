import type { PortMetadata, SourcedField } from "../../api";

/** Display a Decimal-string measurement with a unit, or an em dash if empty. */
export function measure(value: string | null | undefined, unit: string): string {
  if (value === null || value === undefined || value === "") return "—";
  // handling_rate 0 is the seed convention for "not published".
  return `${value} ${unit}`;
}

/** Read a sourced metadata field's display value, coping with UNKNOWN. */
export function metaValue(meta: PortMetadata | undefined, key: string): string {
  const field = meta?.[key];
  if (!field) return "UNKNOWN";
  const v = field.value;
  if (Array.isArray(v)) return v.join(", ");
  return v ?? "UNKNOWN";
}

/** Return the {source, source_date} for a metadata field, if present. */
export function metaSource(
  meta: PortMetadata | undefined,
  key: string,
): SourcedField | undefined {
  return meta?.[key];
}

export const isUnknown = (value: string): boolean =>
  value === "UNKNOWN" || value === "" || value === "—";
