import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithRouter } from "../../test/utils";
import DecisionPage from "../DecisionPage";
import { api } from "../../api";
import type { DecisionResult } from "../../api";

vi.mock("../../api", async () => {
  const actual = await vi.importActual<typeof import("../../api")>("../../api");
  return { ...actual, api: { decision: { evaluate: vi.fn() } } };
});

const evalMock = api.decision.evaluate as unknown as ReturnType<typeof vi.fn>;

const result: DecisionResult = {
  request: {},
  scenario: { freight_change_pct: null, congestion_score: null, vessel_availability: null },
  market: { index: 62, classification: "TIGHT", factors: [], inputs: {}, missing_factors: [] },
  freight_forecast: {
    lane: {}, band: { low: "20.00", mid: "22.00", high: "24.00" }, working_rate: "22.00",
    source: "FreightForecast", freight_model: "freight_gbm_xgboost",
    freight_model_version: "0.2.0", generated_at: "2026-09-01T00:00:00Z",
  },
  recommended_vessel: {
    vessel_id: 1, vessel_name: "Pana Fit", imo: "4200001", vessel_type: "panamax",
    suitability_score: 88, compatibility: { status: "COMPATIBLE" }, estimated_freight: null,
    eta: null, demurrage: null, risk: {}, estimated_total_cost: { amount: "6200000", currency: "USD", unit: "total" },
    suitability: {}, voyage_economics: null,
  },
  compatibility: { status: "COMPATIBLE" },
  congestion: { score: 55 },
  eta: null,
  demurrage: { amount: "40000", currency: "USD", unit: "total" },
  total_landed_cost: { amount: "6200000", currency: "USD", unit: "total" },
  recommended_contract: {
    recommended_strategy: "MULTI_VOYAGE", expected_cost: "1455300.00", expected_savings: "94700.00",
    risk_score: 25, reason: "Lowest risk-adjusted cost.", options: [], currency: "USD",
  },
  risk: {
    overall_score: 48, risk_level: "MEDIUM",
    factors: [{ factor: "freight", raw_value: 0.5, normalized: 0.5, weight: 0.5, contribution: 25, available: true, note: "vol" }],
    inputs: {}, unknown_factors: [],
  },
  timing_decision: "FIX_NOW",
  timing: { decision: "FIX_NOW", expected_move_pct: 0.02, effective_confidence: 0.74, drivers: {}, reason: "Rates expected to rise." },
  expected_savings: { amount: "94700.00", currency: "USD" },
  confidence: 0.74,
  ranked_vessels: [],
  excluded_vessels: [],
  explainability: {
    reasons: ["Recommended Pana Fit (panamax)."], positive_factors: ["Market is TIGHT."],
    negative_factors: [], model_version: { freight_model_version: "0.2.0" }, data_freshness: [],
  },
  notes: [],
};

describe("DecisionPage", () => {
  beforeEach(() => evalMock.mockReset());

  it("runs the unified decision and shows the recommendation + all sections", async () => {
    evalMock.mockResolvedValue(result);
    renderWithRouter(<DecisionPage />);
    await userEvent.click(screen.getByRole("button", { name: /Run decision/i }));

    await waitFor(() => expect(screen.getByLabelText("Recommendation")).toBeInTheDocument());
    // Highly visible decision verb.
    expect(screen.getByText("FIX NOW")).toBeInTheDocument();
    // Section headings present (some labels also appear inside the decision
    // card, so allow multiple matches).
    for (const s of ["Market", "Forecast", "Vessel", "Port", "ETA", "Cost", "Risk", "Contract"]) {
      expect(screen.getAllByText(s).length).toBeGreaterThan(0);
    }
    // Explainability reasons rendered.
    expect(screen.getByText(/Recommended Pana Fit/i)).toBeInTheDocument();
  });

  it("sends scenario overrides when provided", async () => {
    evalMock.mockResolvedValue(result);
    renderWithRouter(<DecisionPage />);
    await userEvent.type(screen.getByLabelText(/Freight change/i), "10");
    await userEvent.click(screen.getByRole("button", { name: /Run decision/i }));
    await waitFor(() => expect(evalMock).toHaveBeenCalled());
    const arg = evalMock.mock.calls[0][0];
    expect(arg.scenario).toEqual({ freight_change_pct: 10 });
  });

  // NOTE: the error-render path (ErrorState on a failed call) is covered by
  // CharteringPage.test — the two pages share the exact same catch → ErrorState
  // pattern. It is intentionally not duplicated here.
});
