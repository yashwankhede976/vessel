/**
 * Unified decision API — the intelligent decision layer.
 *
 * `evaluate` composes forecast + vessel + port + ETA + cost + contract + risk +
 * timing into one explainable recommendation; `ask` answers a grounded question.
 * Thin POST wrappers; all logic lives in the backend (rule: no duplication).
 */
import { post } from "../client";
import type { DecisionResult, AssistantAnswer } from "../resources";

export interface ScenarioInput {
  freight_change_pct?: number | null;
  congestion_score?: number | null;
  vessel_availability?: number | null;
}

export interface DecisionInput {
  commodity: string;
  cargo_quantity: string | number;
  origin: string;
  destination: string;
  laycan_start: string;
  laycan_end: string;
  required_arrival?: string | null;
  currency?: string;
  scenario?: ScenarioInput;
}

export const decisionApi = {
  evaluate(input: DecisionInput): Promise<DecisionResult> {
    return post<DecisionResult>("decision/", input);
  },
  ask(question: string): Promise<AssistantAnswer> {
    return post<AssistantAnswer>("decision/assistant/", { question });
  },
};
