/**
 * Resource types mirroring the backend domain models (catalog / operations /
 * decisions apps). Decimal fields are typed as `string` because DRF serializes
 * DecimalField to a string to preserve precision (no lossy floats).
 *
 * These are intentionally read-oriented; write payloads are declared inline in
 * the relevant domain module when needed.
 */

// ---- catalog ----
export type Coast = "east_coast_india" | "west_coast_india" | "overseas" | "other";
export type PortType = "seaport" | "river" | "anchorage" | "terminal";

export interface Port {
  id: number;
  name: string;
  country: string;
  coast: Coast;
  coast_display: string;
  unlocode: string;
  latitude: string;
  longitude: string;
  port_type: PortType;
  port_type_display: string;
  berth_count: number;
  created_at: string;
  updated_at: string;
}

export interface Berth {
  id: number;
  port_id: number;
  port_name: string;
  berth_name: string;
  max_loa: string;
  max_beam: string;
  max_draft: string;
  handling_rate: string;
  supported_commodities: string[];
  special_constraints: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

/** A single curated field with provenance: {value, source, source_date}. */
export interface SourcedField {
  value: string | string[];
  source: string;
  source_date: string;
}

/** Port.metadata is a bag of sourced fields keyed by name (see seed dataset). */
export type PortMetadata = Record<string, SourcedField | undefined>;

export interface PortDetail extends Port {
  metadata: PortMetadata;
  berths: Berth[];
}

export interface PortConstraints {
  id: number;
  name: string;
  coast: Coast;
  berth_count: number;
  max_loa: string | null;
  max_beam: string | null;
  max_draft: string | null;
  max_handling_rate: string | null;
  supported_commodities: string[];
}

export type VesselType =
  | "handysize"
  | "supramax"
  | "ultramax"
  | "panamax"
  | "kamsarmax"
  | "post_panamax"
  | "capesize"
  | "other";

export type AvailabilityStatus =
  | "open"
  | "laden"
  | "ballast"
  | "fixed"
  | "unknown";

export interface LatestPosition {
  latitude: string;
  longitude: string;
  sog: string | null;
  cog: string | null;
  heading: string | null;
  nav_status: string;
  timestamp: string;
}

export interface Vessel {
  id: number;
  imo: string;
  mmsi: string | null;
  name: string;
  vessel_type: VesselType;
  vessel_type_display: string;
  dwt: string;
  loa: string;
  beam: string;
  draft: string;
  flag: string;
  year_built: number | null;
  speed: string | null;
  availability_status: AvailabilityStatus;
  availability_status_display: string;
  open_date: string | null;
  latest_position: LatestPosition | null;
  created_at: string;
  updated_at: string;
}

export interface Commodity {
  id: number;
  name: string;
  category: string;
  hs_code: string;
  description: string;
}

export interface CargoRequirement {
  id: number;
  reference: string;
  commodity: number;
  destination_port: number;
  preferred_origin: number | null;
  quantity_tonnes: string;
  tolerance_pct: string;
  laycan_start: string;
  laycan_end: string;
  target_price_per_tonne: string | null;
  currency: string;
  status: string;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface FreightObservation {
  id: number;
  route: number;
  vessel_type: VesselType | "";
  observed_on: string;
  rate_per_tonne: string;
  currency: string;
  rate_type: string;
  source: string;
  is_estimated: boolean;
}

// ---- operations (forecasts / risk / recommendations / alerts) ----
export interface FreightForecast {
  id: number;
  route: number;
  vessel_type: string;
  generated_at: string;
  target_date: string;
  horizon: "short_term" | "medium_term";
  predicted_rate_per_tonne: string;
  lower_bound: string | null;
  upper_bound: string | null;
  currency: string;
  model_name: string;
  model_version: string;
}

export interface ETAForecast {
  id: number;
  vessel: number;
  destination_port: number;
  route: number | null;
  generated_at: string;
  predicted_eta: string;
  uncertainty_hours: string | null;
  model_name: string;
  model_version: string;
}

export interface Recommendation {
  id: number;
  rec_type: string;
  generated_at: string;
  cargo_requirement: number | null;
  route: number | null;
  origin: number | null;
  destination_port: number | null;
  vessel: number | null;
  summary: string;
  confidence: string | null;
  estimated_impact: string | null;
  currency: string;
  explanation: Record<string, unknown>;
  inputs: Record<string, unknown>;
  model_name: string;
  model_version: string;
}

/** Placeholder alert shape (backend model TBD in a later task). */
export interface Alert {
  id: number;
  alert_type: string;
  severity: "low" | "medium" | "high";
  message: string;
  created_at: string;
  acknowledged: boolean;
}

// ---- decisions (scenarios / optimization) ----
export interface Scenario {
  id: number;
  name: string;
  description: string;
  cargo_requirement: number | null;
  is_baseline: boolean;
  parameters: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface OptimizationRun {
  id: number;
  run_type: string;
  cargo_requirement: number | null;
  scenario: number | null;
  status: "pending" | "running" | "completed" | "failed";
  started_at: string | null;
  finished_at: string | null;
  solver: string;
  solver_version: string;
  parameters: Record<string, unknown>;
  error_message: string;
  created_at: string;
  updated_at: string;
}

export interface OptimizationResult {
  id: number;
  run: number;
  strategy: number | null;
  contract_plan: number | null;
  rank: number;
  is_optimal: boolean;
  objective_value: string | null;
  currency: string;
  expected_cost: string | null;
  expected_savings: string | null;
  detail: Record<string, unknown>;
}
