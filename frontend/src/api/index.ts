/**
 * Centralized API client entry point.
 *
 * Import the aggregated `api` object for typed, per-domain calls:
 *   import { api } from "../api";
 *   const ports = await api.ports.list({ coast: "east_coast_india" });
 *
 * Or import individual pieces (types, hooks, error class) as needed.
 */
import { portsApi, berthsApi } from "./endpoints/ports";
import { vesselsApi } from "./endpoints/vessels";
import { cargoApi } from "./endpoints/cargo";
import { freightApi } from "./endpoints/freight";
import { forecastsApi } from "./endpoints/forecasts";
import { recommendationsApi } from "./endpoints/recommendations";
import { alertsApi } from "./endpoints/alerts";
import { scenariosApi } from "./endpoints/scenarios";
import { optimizationApi } from "./endpoints/optimization";
import { analyticsApi } from "./endpoints/analytics";
import { systemApi } from "./endpoints/system";

/** Aggregated, typed API surface grouped by domain. */
export const api = {
  ports: portsApi,
  berths: berthsApi,
  vessels: vesselsApi,
  cargo: cargoApi,
  freight: freightApi,
  forecasts: forecastsApi,
  recommendations: recommendationsApi,
  alerts: alertsApi,
  scenarios: scenariosApi,
  optimization: optimizationApi,
  // Decision-support engines + system observability (real backend endpoints).
  analytics: analyticsApi,
  system: systemApi,
};

// Core client controls (interceptors) for app bootstrap.
export { addRequestInterceptor } from "./client";
export { ApiError } from "./errors";
export type { ApiErrorKind } from "./errors";
export { useApi } from "./useApi";
export type { ApiState } from "./useApi";

// Shared and resource types.
export type * from "./types";
export type * from "./resources";
