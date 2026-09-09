/**
 * Centralized HTTP client for the Vessel API.
 *
 * One abstraction over fetch that provides:
 * - a configurable base URL (VITE_API_BASE_URL)
 * - a request interceptor hook (e.g. to inject auth headers later)
 * - timeout handling via AbortController
 * - safe retry (idempotent GET only, on transient errors, with backoff)
 * - backend-envelope unwrapping ({success,data,errors,pagination})
 * - error normalization to ApiError
 *
 * Domain modules (ports, vessels, …) are built on top of this and never call
 * fetch directly.
 */
import { ApiError } from "./errors";
import type { ApiEnvelope, Paginated, Pagination } from "./types";

type QueryValue = string | number | boolean | undefined | null;
export type QueryParams = Record<string, QueryValue>;

export interface RequestOptions {
  /** Query-string parameters (undefined/null values are dropped). */
  params?: QueryParams;
  /** JSON request body (for POST/PUT/PATCH). */
  body?: unknown;
  /** Per-request timeout override (ms). */
  timeoutMs?: number;
  /** Per-request retry override (GET only). */
  retries?: number;
  /** Caller-supplied abort signal (cancellation). */
  signal?: AbortSignal;
  /** Extra headers for this request. */
  headers?: Record<string, string>;
}

/** A hook that can mutate the outgoing request config (e.g. add auth). */
export type RequestInterceptor = (init: RequestInit & { headers: Headers }) =>
  | void
  | Promise<void>;

interface ClientConfig {
  baseUrl: string;
  defaultTimeoutMs: number;
  defaultRetries: number;
}

const DEFAULT_CONFIG: ClientConfig = {
  baseUrl:
    (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ??
    "http://localhost:8000/api/v1",
  defaultTimeoutMs: 15000,
  defaultRetries: 2,
};

const interceptors: RequestInterceptor[] = [];

/** Register a request interceptor (applied in registration order). */
export function addRequestInterceptor(interceptor: RequestInterceptor): void {
  interceptors.push(interceptor);
}

function buildUrl(path: string, params?: QueryParams): string {
  const base = DEFAULT_CONFIG.baseUrl;
  const url = new URL(
    `${base}/${path.replace(/^\//, "")}`,
    // A base is required by URL when the configured base is relative.
    typeof window !== "undefined" ? window.location.origin : "http://localhost",
  );
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, String(value));
      }
    }
  }
  return url.toString();
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

const isMethodSafe = (method: string) => method.toUpperCase() === "GET";

async function parseEnvelope<T>(response: Response): Promise<ApiEnvelope<T>> {
  const text = await response.text();
  if (!text) {
    // Empty body (e.g. 204). Treat as success with null data.
    return { success: true, data: null as unknown as T, errors: null };
  }
  try {
    return JSON.parse(text) as ApiEnvelope<T>;
  } catch {
    throw new ApiError("parse", "Response body was not valid JSON.", {
      status: response.status,
    });
  }
}

async function doFetch<T>(
  method: string,
  url: string,
  options: RequestOptions,
): Promise<{ data: T; pagination: Pagination | null }> {
  const controller = new AbortController();
  const timeoutMs = options.timeoutMs ?? DEFAULT_CONFIG.defaultTimeoutMs;
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  // Chain a caller-provided signal to our controller.
  if (options.signal) {
    if (options.signal.aborted) controller.abort();
    else options.signal.addEventListener("abort", () => controller.abort());
  }

  const headers = new Headers({ Accept: "application/json", ...options.headers });
  const init: RequestInit & { headers: Headers } = {
    method,
    headers,
    signal: controller.signal,
  };
  if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
    init.body = JSON.stringify(options.body);
  }

  // Request interceptors (auth, correlation ids, …).
  for (const interceptor of interceptors) {
    await interceptor(init);
  }

  let response: Response;
  try {
    response = await fetch(url, init);
  } catch (err) {
    // Distinguish timeout/cancellation from a genuine network failure.
    if (controller.signal.aborted) {
      const kind = options.signal?.aborted ? "aborted" : "timeout";
      throw new ApiError(kind, kind === "timeout" ? "Request timed out." : "Request cancelled.");
    }
    throw new ApiError("network", "Network request failed.");
  } finally {
    clearTimeout(timeout);
  }

  const envelope = await parseEnvelope<T>(response);

  if (!response.ok || envelope.success === false) {
    const items = envelope.success === false ? envelope.errors : [];
    const message =
      items.length > 0 ? items.map((i) => i.detail).join(" ") : `Request failed (${response.status}).`;
    throw new ApiError("http", message, { status: response.status, items });
  }

  return {
    data: envelope.data,
    pagination: envelope.pagination ?? null,
  };
}

/** Core request with safe retry for idempotent GETs. */
export async function request<T>(
  method: string,
  path: string,
  options: RequestOptions = {},
): Promise<{ data: T; pagination: Pagination | null }> {
  const url = buildUrl(path, options.params);
  const maxRetries = isMethodSafe(method)
    ? options.retries ?? DEFAULT_CONFIG.defaultRetries
    : 0; // never retry non-idempotent methods

  let attempt = 0;
  // Attempts = 1 + retries.
  for (;;) {
    try {
      return await doFetch<T>(method, url, options);
    } catch (err) {
      const apiError = err instanceof ApiError ? err : new ApiError("network", "Unexpected error.");
      const canRetry =
        attempt < maxRetries && apiError.isRetryable && apiError.kind !== "aborted";
      if (!canRetry) throw apiError;
      // Exponential backoff: 300ms, 600ms, …
      await sleep(300 * 2 ** attempt);
      attempt += 1;
    }
  }
}

/** GET returning a single typed value. */
export async function get<T>(path: string, options?: RequestOptions): Promise<T> {
  const { data } = await request<T>("GET", path, options);
  return data;
}

/** GET returning a paginated list (items + pagination metadata). */
export async function getList<T>(
  path: string,
  options?: RequestOptions,
): Promise<Paginated<T>> {
  const { data, pagination } = await request<T[]>("GET", path, options);
  return { items: data ?? [], pagination };
}

/** POST returning a single typed value. Not retried (non-idempotent). */
export async function post<T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
  const { data } = await request<T>("POST", path, { ...options, body });
  return data;
}

/** PATCH returning a single typed value. Not retried. */
export async function patch<T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
  const { data } = await request<T>("PATCH", path, { ...options, body });
  return data;
}

/** DELETE. Not retried. */
export async function del<T = void>(path: string, options?: RequestOptions): Promise<T> {
  const { data } = await request<T>("DELETE", path, options);
  return data;
}
