/**
 * Decision-support analytics API — the deterministic engines exposed by the
 * backend under /api/v1/. Every method is a thin typed wrapper over the shared
 * client (POST for compute endpoints, GET for the composed freight forecast).
 *
 * NO business logic lives here — the frontend only sends inputs and renders the
 * backend's response (rule: React must not duplicate backend logic).
 */
import { get, post } from "../client";
import type {
  AlternativePortResult,
  ContractPortfolioResult,
  CongestionForecastResult,
  ETAResult,
  FixWaitResult,
  FreightForecastResponse,
  IdleVesselResult,
  LandedCostResult,
  MarketPressureResult,
  OptimizationResultDTO,
  OriginComparison,
  RiskResult,
  SpotVsContractResult,
  VesselRecommendationResult,
  VoyageEconomicsResult,
} from "../resources";

// --- request payload shapes (mirror the DRF serializers) ---
export interface MarketPressureInput {
  vessel_supply?: number;
  cargo_demand?: number;
  freight_volatility?: number;
  port_congestion?: number;
  ton_mile_demand?: number;
  bunker?: number;
  seasonality?: number;
}

export interface RiskInput {
  freight_volatility?: number;
  port_congestion?: number;
  weather_risk?: number;
  eta_delay_probability?: number;
  expected_demurrage_cost?: number;
  commodity_volatility?: number;
  fx_volatility?: number;
  geopolitical_risk?: number;
}

export interface FixWaitInput {
  current_rate: string | number;
  forecast_7d?: string | number | null;
  forecast_14d?: string | number | null;
  forecast_30d?: string | number | null;
  confidence_7d?: number | null;
  confidence_14d?: number | null;
  confidence_30d?: number | null;
  days_to_deadline?: number | null;
  vessel_availability?: number | null;
  congestion_score?: number | null;
  freight_volatility?: number | null;
}

export interface VoyageCostInput {
  distance_nm: string | number;
  speed_kn: string | number;
  cargo_tonnes: string | number;
  bunker_rate_tpd?: string | number;
  bunker_price_per_tonne?: string | number;
  bunker_idle_rate_tpd?: string | number | null;
  port_days?: string | number;
  port_cost?: string | number;
  freight_cost?: string | number | null;
  freight_rate_per_tonne?: string | number | null;
  canal_cost?: string | number;
  misc_cost?: string | number;
  demurrage_rate_per_day?: string | number | null;
  expected_demurrage_days?: string | number | null;
  estimated_demurrage?: string | number | null;
  currency?: string;
}

export interface CostComponentInput {
  amount: string | number | null;
  currency?: string;
}
export interface LandedCostInput {
  origin: string;
  destination: string;
  cargo_tonnes: string | number;
  commodity_cost?: CostComponentInput;
  freight_cost?: CostComponentInput;
  bunker_cost?: CostComponentInput;
  port_charges?: CostComponentInput;
  handling_cost?: CostComponentInput;
  demurrage_cost?: CostComponentInput;
  insurance_other_cost?: CostComponentInput;
  target_currency?: string;
  fx_rates?: Record<string, string | number>;
}

export interface SpotVsContractInput {
  spot_freight_per_tonne: string | number;
  cargo_tonnes: string | number;
  freight_volatility?: number;
  base_demurrage_cost?: string | number | null;
  non_freight_cost?: string | number | null;
  congestion_score?: number | null;
  currency?: string;
}
export interface ContractPortfolioInput {
  total_tonnes: string | number;
  spot_freight_per_tonne: string | number;
  market_pressure_index?: number | null;
  freight_volatility?: number | null;
  currency?: string;
}

export interface CandidateVoyageInput {
  id: string;
  origin: string;
  destination: string;
  vessel_type: string;
  contract_strategy?: string;
  cost_per_voyage: string | number;
  capacity_tonnes: string | number;
  max_voyages?: number;
  feasible_in_laycan?: boolean;
  is_compatible?: boolean;
}
export interface OptimizationInput {
  required_tonnes: string | number;
  candidates: CandidateVoyageInput[];
  tolerance_pct?: string | number;
  currency?: string;
  destination_capacity?: Record<string, number>;
  origin_min_tonnes?: Record<string, number>;
  origin_max_tonnes?: Record<string, number>;
  contract_min_voyages?: Record<string, number>;
  contract_max_voyages?: Record<string, number>;
  time_limit_ms?: number;
}

export interface AlternativePortInput {
  origin: string;
  requested_destination: string;
  cargo_tonnes: string | number;
  commodity: string;
  vessel_id?: number | null;
  bunker_price_per_tonne?: string | number | null;
  freight_rate_per_tonne?: string | number | null;
  currency?: string;
}

export interface EmploymentOpportunityInput {
  name: string;
  laden_distance_nm: string | number;
  cargo_tonnes: string | number;
  freight_rate_per_tonne: string | number;
  ballast_distance_nm?: string | number | null;
  discharge_port_id?: number | null;
  commodity?: string | null;
  port_cost?: string | number | null;
  bunker_price_per_tonne?: string | number | null;
}
export interface IdleVesselInput {
  vessel_id: number;
  opportunities: EmploymentOpportunityInput[];
  currency?: string;
}

export interface ETARequestInput {
  route_distance_nm: number;
  speed_kn: number;
  latitude?: number | null;
  longitude?: number | null;
  weather_risk?: number;
  destination_congestion?: number;
  expected_port_waiting_days?: number;
}

export interface CongestionForecastInput {
  vessels_near_port?: number | null;
  vessels_waiting?: number | null;
  historical_traffic?: number | null;
  expected_arrivals?: number | null;
  throughput_utilization?: number | null;
  weather_warning?: string | null;
  recent_waiting_time_days?: number | null;
  trend_per_day?: number | null;
}

export interface RecommendVesselsInput {
  origin: string;
  destination: string;
  cargo_tonnes: string | number;
  commodity: string;
  laycan_start: string;
  laycan_end: string;
  currency?: string;
  bunker_price_per_tonne?: string | number | null;
  only_available?: boolean;
}

export interface FreightForecastQuery {
  origin: string;
  destination: string;
  vessel_type?: string;
  horizon?: "short_term" | "medium_term";
  history_days?: number;
}

/** The decision-support engine surface. */
export const analyticsApi = {
  marketPressure(input: MarketPressureInput): Promise<MarketPressureResult> {
    return post<MarketPressureResult>("market-pressure/", input);
  },
  risk(input: RiskInput): Promise<RiskResult> {
    return post<RiskResult>("risk/", input);
  },
  fixWait(input: FixWaitInput): Promise<FixWaitResult> {
    return post<FixWaitResult>("fix-wait/", input);
  },
  voyageCost(input: VoyageCostInput): Promise<VoyageEconomicsResult> {
    return post<VoyageEconomicsResult>("voyage-cost/", input);
  },
  landedCost(input: LandedCostInput): Promise<LandedCostResult> {
    return post<LandedCostResult>("landed-cost/", input);
  },
  compareOrigins(inputs: LandedCostInput[]): Promise<OriginComparison> {
    return post<OriginComparison>("landed-cost/compare/", { inputs });
  },
  spotVsContract(input: SpotVsContractInput): Promise<SpotVsContractResult> {
    return post<SpotVsContractResult>("contract-strategy/compare/", input);
  },
  contractPortfolio(input: ContractPortfolioInput): Promise<ContractPortfolioResult> {
    return post<ContractPortfolioResult>("contract-strategy/portfolio/", input);
  },
  optimizeMultiVoyage(input: OptimizationInput): Promise<OptimizationResultDTO> {
    return post<OptimizationResultDTO>("optimization/multi-voyage/", input);
  },
  alternativePort(input: AlternativePortInput): Promise<AlternativePortResult> {
    return post<AlternativePortResult>("alternative-port/", input);
  },
  idleVessel(input: IdleVesselInput): Promise<IdleVesselResult> {
    return post<IdleVesselResult>("idle-vessel/", input);
  },
  eta(input: ETARequestInput): Promise<ETAResult> {
    return post<ETAResult>("eta/", input);
  },
  congestionForecast(input: CongestionForecastInput): Promise<CongestionForecastResult> {
    return post<CongestionForecastResult>("congestion/forecast/", input);
  },
  recommendVessels(input: RecommendVesselsInput): Promise<VesselRecommendationResult> {
    return post<VesselRecommendationResult>("recommendations/vessels/", input);
  },
  freightForecast(
    query: FreightForecastQuery,
    signal?: AbortSignal,
  ): Promise<FreightForecastResponse> {
    return get<FreightForecastResponse>("forecasts/freight/", {
      params: { ...query },
      signal,
    });
  },
};
