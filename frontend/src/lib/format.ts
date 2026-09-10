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

/**
 * Display currency. The backend computes financials in USD and never guesses an
 * FX rate. For an India-facing demo we present figures in INR using a single,
 * approximate, clearly-labelled conversion rate. This is an ESTIMATED display
 * conversion — the underlying stored values remain USD.
 */
const DISPLAY_CURRENCY = "INR";
const USD_TO_INR = 83; // approximate; display-only

/** Convert a plain amount from `fromCurrency` into the display currency. */
function toDisplayAmount(
  amount: string | number,
  fromCurrency: string,
): { amount: number; currency: string } {
  const num = typeof amount === "number" ? amount : Number(amount);
  // Only convert real USD figures; leave other codes (or the empty-code
  // "format a bare number" callers) exactly as given.
  if (fromCurrency === "USD" && !Number.isNaN(num)) {
    return { amount: num * USD_TO_INR, currency: DISPLAY_CURRENCY };
  }
  return { amount: num, currency: fromCurrency };
}

/** Format a numeric string with thousands separators (no rounding surprises). */
export function formatNumber(value: string | number | null | undefined, maxFractionDigits = 2): string {
  if (value == null || value === "") return "\u2014";
  const num = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(num)) return String(value);
  return num.toLocaleString(undefined, { maximumFractionDigits: maxFractionDigits });
}

/** Format a backend Money object as e.g. "\u20b9575,190,000.00" with a unit suffix.
 * USD amounts are shown in INR via a display-only conversion (see DISPLAY_CURRENCY). */
export function formatMoney(money: Money | null | undefined): string {
  if (!money || money.amount == null) return "\u2014";
  const { amount, currency } = toDisplayAmount(money.amount, money.currency);
  const symbol = CURRENCY_SYMBOL[currency] ?? `${currency} `;
  const unitSuffix =
    money.unit === "per_tonne" ? " /t" : money.unit === "per_day" ? " /day" : "";
  return `${symbol}${formatNumber(amount)}${unitSuffix}`;
}

/** Format a currency amount given as a plain Decimal string + code.
 * USD amounts are shown in INR via a display-only conversion. An empty currency
 * code is a caller convention for "format a bare number" and is left untouched. */
export function formatCurrency(
  amount: string | number | null | undefined,
  currency = "USD",
): string {
  if (amount == null || amount === "") return "\u2014";
  const conv = toDisplayAmount(amount, currency);
  const symbol = CURRENCY_SYMBOL[conv.currency] ?? `${conv.currency} `;
  return `${symbol}${formatNumber(conv.amount)}`;
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
