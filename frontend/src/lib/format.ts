/**
 * Shared display formatters. Money values from the backend are Decimal strings;
 * these format them for the UI without losing the original precision in state.
 */
import type { Money } from "../api";

const CURRENCY_SYMBOL: Record<string, string> = {
  USD: "$",
  INR: "\u20b9",
  EUR: "\u20ac",
  GBP: "\u00a3",
};

/** Format a numeric string with thousands separators (no rounding surprises). */
export function formatNumber(value: string | number | null | undefined, maxFractionDigits = 2): string {
  if (value == null || value === "") return "\u2014";
  const num = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(num)) return String(value);
  return num.toLocaleString(undefined, { maximumFractionDigits: maxFractionDigits });
}

/** Format a backend Money object as e.g. "$6,930,000.00" with a unit suffix. */
export function formatMoney(money: Money | null | undefined): string {
  if (!money || money.amount == null) return "\u2014";
  const symbol = CURRENCY_SYMBOL[money.currency] ?? `${money.currency} `;
  const amount = formatNumber(money.amount);
  const unitSuffix =
    money.unit === "per_tonne" ? " /t" : money.unit === "per_day" ? " /day" : "";
  return `${symbol}${amount}${unitSuffix}`;
}

/** Format a currency amount given as a plain Decimal string + code. */
export function formatCurrency(
  amount: string | number | null | undefined,
  currency = "USD",
): string {
  if (amount == null || amount === "") return "\u2014";
  const symbol = CURRENCY_SYMBOL[currency] ?? `${currency} `;
  return `${symbol}${formatNumber(amount)}`;
}

/** Format a 0..1 fraction as a percentage string. */
export function formatPercent(value: number | null | undefined, digits = 0): string {
  if (value == null) return "\u2014";
  return `${(value * 100).toFixed(digits)}%`;
}

/** Title-case an ENUM_VALUE or snake_case string for display. */
export function humanize(value: string | null | undefined): string {
  if (!value) return "\u2014";
  return value
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
