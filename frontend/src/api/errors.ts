/**
 * Normalized API error. Every failure path in the HTTP client throws an
 * ApiError, so callers have one consistent error shape regardless of whether
 * the failure was a network error, timeout, non-2xx response, or a malformed
 * body.
 */
import type { ApiErrorItem } from "./types";

export type ApiErrorKind =
  | "network" // request never completed (offline, DNS, CORS, etc.)
  | "timeout" // aborted after exceeding the configured timeout
  | "http" // server returned a non-2xx status
  | "parse" // response body could not be parsed / unexpected shape
  | "aborted"; // caller cancelled the request

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  /** HTTP status code, when the failure was an HTTP error. */
  readonly status: number | null;
  /** Normalized error items from the backend envelope, if any. */
  readonly items: ApiErrorItem[];

  constructor(
    kind: ApiErrorKind,
    message: string,
    options: { status?: number | null; items?: ApiErrorItem[] } = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    this.status = options.status ?? null;
    this.items = options.items ?? [];
  }

  /** True for errors that are typically transient and safe to retry. */
  get isRetryable(): boolean {
    if (this.kind === "network" || this.kind === "timeout") return true;
    if (this.kind === "http" && this.status !== null) {
      return this.status >= 500 || this.status === 429;
    }
    return false;
  }

  /** A single human-readable message suitable for UI display. */
  get displayMessage(): string {
    if (this.items.length > 0) {
      return this.items.map((i) => i.detail).join(" ");
    }
    return this.message;
  }
}
