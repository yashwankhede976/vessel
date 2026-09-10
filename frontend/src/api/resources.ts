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

// ===========================================================================
// Decision-support engines (analytics endpoints).
//
// These mirror the deterministic engine responses (market pressure, risk,
// fix/wait, voyage cost, landed cost, contract strategy, optimization,
// alternative port, idle vessel, congestion forecast) and the recommendation
// composition. Monetary values are strings (Decimal precision) where the
// backend returns Decimals; scores/indices are numbers (0..100 / 0..1).
// ===========================================================================

/** A money value that always carries currency + unit (backend Money.to_dict). */
export interface Money {
  amount: string;
  currency: string;
  unit: string; // "total" | "per_tonne" | "per_day" | "per_tonne_km"
}

// ---- market pressure ----
export interface PressureFactor {
  factor: string;
  raw_value: unknown;
  normalized: number;
  weight: number;
  contribution: number;
  available: boolean;
  note: string;
}
export interface MarketPressureResult {
  index: number; // 0..100
  classification: string; // VERY_WEAK | WEAK | NEUTRAL | TIGHT | EXTREMELY_TIGHT
  factors: PressureFactor[];
  inputs: Record<string, unknown>;
  missing_factors: string[];
}

// ---- risk ----
export interface RiskFactor {
  factor: string;
  raw_value: unknown;
  normalized: number | null; // null => UNKNOWN
  weight: number;
  contribution: number;
  available: boolean;
  note: string;
}
export interface RiskResult {
  overall_score: number; // 0..100
  risk_level: string; // LOW | MEDIUM | HIGH
  factors: RiskFactor[];
  inputs: Record<string, unknown>;
  unknown_factors: string[];
}

// ---- fix / wait ----
export interface FixWaitResult {
  decision: string; // FIX_NOW | WAIT | PARTIAL_FIX | MONITOR
  expected_move_pct: number | null;
  effective_confidence: number | null;
  drivers: Record<string, unknown>;
  reason: string;
}

// ---- voyage economics ----
export interface VoyageEconomicsResult {
  currency: string;
  distance_nm: string;
  distance_km: string;
  sailing_days: string;
  port_days: string;
  total_days: string;
  cargo_tonnes: string;
  bunker_consumption_tonnes: string;
  cost_components: Record<string, Money>;
  total_voyage_cost: Money;
  cost_per_tonne: Money | null;
  cost_per_day: Money | null;
  cost_per_tonne_km: Money | null;
  inputs: Record<string, unknown>;
}

// ---- landed cost ----
export interface LandedCostResult {
  origin: string;
  destination: string;
  currency: string;
  cargo_tonnes: string;
  components: Record<string, Money>;
  total_landed_cost: Money;
  landed_cost_per_tonne: Money | null;
  fx_rates_used: Record<string, string>;
  missing_components: string[];
}
export interface OriginComparisonEntry {
  origin: string;
  destination: string;
  total_landed_cost: Money;
  landed_cost_per_tonne: Money | null;
  delta_vs_cheapest: Money;
  is_cheapest: boolean;
}
export interface OriginComparison {
  destination: string;
  currency: string;
  entries: OriginComparisonEntry[];
}

// ---- spot vs contract + portfolio ----
export interface StrategyOption {
  strategy: string;
  expected_freight_per_tonne: string;
  expected_freight_cost: string;
  volatility_exposure: number;
  flexibility: number;
  volume_commitment: number;
  expected_demurrage: string;
  total_cost: string;
  risk_score: number;
  risk_adjusted_cost: string;
  currency: string;
}
export interface SpotVsContractResult {
  recommended_strategy: string;
  expected_cost: string;
  expected_savings: string;
  risk_score: number;
  reason: string;
  options: StrategyOption[];
  currency: string;
}
export interface PortfolioAllocation {
  strategy: string;
  share: number;
  tonnes: string;
  freight_per_tonne: string;
  cost: string;
  volatility_exposure: number;
}
export interface ContractPortfolioResult {
  regime: string;
  allocations: PortfolioAllocation[];
  expected_cost: string;
  all_spot_cost: string;
  estimated_savings: string;
  risk_reduction: number;
  currency: string;
  reason: string;
}

// ---- multi-voyage optimization ----
export interface SelectedVoyage {
  candidate_id: string;
  origin: string;
  destination: string;
  vessel_type: string;
  contract_strategy: string;
  voyages: number;
  tonnes: string;
  cost: string;
}
export interface OptimizationResultDTO {
  status: string; // optimal | feasible
  selected_voyages: SelectedVoyage[];
  origin_allocation: Record<string, string>;
  destination_allocation: Record<string, string>;
  vessel_type_allocation: Record<string, string>;
  contract_strategy_mix: Record<string, number>;
  total_cost: string;
  total_tonnes: string;
  estimated_savings: string;
  currency: string;
  notes: string[];
}

// ---- alternative port ----
export interface PortComparisonEntry {
  port_id: number;
  port_name: string;
  feasible: boolean;
  compatibility_status: string | null;
  congestion_score: number | null;
  expected_waiting_days: number | null;
  distance_nm: number | null;
  total_cost: string | null;
  estimated_days: number | null;
  currency: string;
  is_requested: boolean;
  notes: string[];
}
export interface AlternativePortResult {
  requested_port: string;
  recommended_port: string | null;
  alternative_ports: PortComparisonEntry[];
  cost_difference: string | null;
  time_difference: number | null;
  currency: string;
  reason: string;
}

// ---- idle vessel ----
export interface RankedOpportunity {
  name: string;
  feasible: boolean;
  compatibility_status: string | null;
  expected_revenue: string;
  expected_cost: string;
  expected_margin: string;
  voyage_days: number | null;
  margin_per_day: string | null;
  currency: string;
  notes: string[];
}
export interface IdleVesselResult {
  vessel_id: number;
  vessel_name: string;
  ranked_opportunities: RankedOpportunity[];
  excluded_opportunities: RankedOpportunity[];
  currency: string;
}

// ---- congestion forecast ----
export interface CongestionHorizon {
  horizon_days: number;
  congestion_score: number;
  expected_waiting_time_days: number;
  confidence: number;
  risk_level: string; // LOW | MEDIUM | HIGH | SEVERE
}
export interface CongestionForecastResult {
  current_score: number;
  current_classification: string;
  trend_per_day: number;
  horizons: CongestionHorizon[];
  missing_signals: string[];
  inputs: Record<string, unknown>;
}

// ---- ETA (prediction endpoint) ----
export interface ETADelayCause {
  cause: string;
  delay_hours: number;
  detail: string;
}
export interface ETAResult {
  eta: string;
  eta_p50: string;
  eta_p80: string;
  eta_p95: string;
  total_hours: number;
  base_transit_hours: number;
  total_delay_hours: number;
  delay_causes: ETADelayCause[];
  delay_probability: number;
  delay_reasons: string[];
  inputs: Record<string, unknown>;
}

// ---- freight forecast (composed GET /forecasts/freight/) ----
export interface FreightForecastPoint {
  target_date: string;
  horizon: string;
  predicted_rate_per_tonne: string;
  lower_bound: string | null;
  upper_bound: string | null;
  confidence: string | null;
  currency: string;
}
export interface FreightHistoricalPoint {
  date: string;
  rate_per_tonne: string;
  currency: string;
  rate_type: string;
  is_estimated: boolean;
  source: string;
}
export interface FreightForecastResponse {
  route: Record<string, unknown> | null;
  historical: FreightHistoricalPoint[];
  forecast: FreightForecastPoint[];
  model: Record<string, unknown> | null;
  data_freshness: Record<string, unknown> | null;
  cached: boolean;
  message?: string;
  query?: Record<string, unknown>;
}

// ---- vessel recommendation (composed POST /recommendations/vessels/) ----
export interface CandidateRecommendation {
  vessel_id: number;
  vessel_name: string;
  imo: string;
  vessel_type: string;
  suitability_score: number;
  compatibility: Record<string, unknown>;
  estimated_freight: Money | null;
  eta: ETAResult | null;
  demurrage: Money | null;
  risk: Record<string, unknown>;
  estimated_total_cost: Money | null;
  suitability: Record<string, unknown>;
  voyage_economics: VoyageEconomicsResult | null;
}
export interface VesselTypeRanking {
  vessel_type: string;
  candidate_count: number;
  best_suitability_score: number;
  avg_suitability_score: number;
}
export interface ExcludedVessel {
  vessel_id: number;
  vessel_name: string;
  imo: string;
  vessel_type: string;
  reason: string;
  compatibility: Record<string, unknown>;
}
export interface VesselRecommendationResult {
  request: Record<string, unknown>;
  route_resolved: boolean;
  ranked_vessels: CandidateRecommendation[];
  ranked_vessel_types: VesselTypeRanking[];
  excluded_vessels: ExcludedVessel[];
  notes: string[];
}

// ---- alerts (real ViewSet) ----
export interface AlertNotification {
  id: number;
  channel: string;
  status: string;
  sent_at: string | null;
  detail: string;
  created_at: string;
}
export interface DecisionAlert {
  id: number;
  alert_type: string;
  severity: "info" | "low" | "medium" | "high" | "critical";
  timestamp: string;
  entity: string;
  route: number | null;
  port: number | null;
  vessel: number | null;
  trigger_value: string | null;
  threshold: string | null;
  message: string;
  recommended_action: string;
  status: "new" | "acknowledged" | "resolved";
  acknowledged_at: string | null;
  resolved_at: string | null;
  context: Record<string, unknown>;
  notifications: AlertNotification[];
  created_at: string;
  updated_at: string;
}

// ---- system observability ----
export interface FreshnessEntry {
  dataset: string;
  latest_at: string | null;
  age_hours: number | null;
  level: "FRESH" | "STALE" | "VERY_STALE" | "UNKNOWN";
  fresh_within_hours: number;
  stale_within_hours: number;
  record_count: number;
}
export interface DataFreshnessResponse {
  generated_at: string;
  datasets: FreshnessEntry[];
}
export interface ExternalServiceHealth {
  provider: string;
  configured: boolean;
  needs_key: boolean;
  reachable: boolean | null;
  last_success: string | null;
  last_failure: string | null;
  data_freshness: FreshnessEntry[];
}
export interface ExternalServicesResponse {
  generated_at: string;
  services: ExternalServiceHealth[];
}
