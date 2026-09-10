import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithRouter } from "../../test/utils";
import CharteringPage from "../CharteringPage";
import { api, ApiError } from "../../api";
import type {
  SpotVsContractResult,
  VesselRecommendationResult,
} from "../../api";

vi.mock("../../api", async () => {
  const actual = await vi.importActual<typeof import("../../api")>("../../api");
  return {
    ...actual,
    api: {
      analytics: {
        recommendVessels: vi.fn(),
        spotVsContract: vi.fn(),
        alternativePort: vi.fn(),
        fixWait: vi.fn(),
      },
    },
  };
});

const a = api.analytics as unknown as {
  recommendVessels: ReturnType<typeof vi.fn>;
  spotVsContract: ReturnType<typeof vi.fn>;
  alternativePort: ReturnType<typeof vi.fn>;
  fixWait: ReturnType<typeof vi.fn>;
};

const recResult: VesselRecommendationResult = {
  request: {}, route_resolved: true,
  ranked_vessels: [
    {
      vessel_id: 1, vessel_name: "Cape One", imo: "1000001", vessel_type: "capesize",
      suitability_score: 82, compatibility: { status: "COMPATIBLE" },
      estimated_freight: { amount: "1200000", currency: "USD", unit: "total" },
      eta: null, demurrage: { amount: "40000", currency: "USD", unit: "total" },
      risk: { risk_level: "MEDIUM", congestion_score: 55 },
      estimated_total_cost: { amount: "6200000", currency: "USD", unit: "total" },
      suitability: {}, voyage_economics: null,
    },
  ],
  ranked_vessel_types: [], excluded_vessels: [], notes: [],
};

const stratResult: SpotVsContractResult = {
  recommended_strategy: "MULTI_VOYAGE", expected_cost: "1455300.00",
  expected_savings: "94700.00", risk_score: 25, reason: "Lowest risk-adjusted cost.",
  options: [
    { strategy: "SPOT", expected_freight_per_tonne: "22", expected_freight_cost: "1", volatility_exposure: 1, flexibility: 1, volume_commitment: 0, expected_demurrage: "0", total_cost: "1550000", risk_score: 43, risk_adjusted_cost: "1", currency: "USD" },
    { strategy: "MULTI_VOYAGE", expected_freight_per_tonne: "20", expected_freight_cost: "1", volatility_exposure: 0.15, flexibility: 0.2, volume_commitment: 1, expected_demurrage: "0", total_cost: "1455300", risk_score: 25, risk_adjusted_cost: "1", currency: "USD" },
  ],
  currency: "USD",
};

describe("CharteringPage", () => {
  beforeEach(() => {
    a.recommendVessels.mockReset();
    a.spotVsContract.mockReset();
    a.alternativePort.mockReset();
    a.fixWait.mockReset();
  });

  it("runs the workflow and shows the decision card, ranking, and strategy", async () => {
    a.recommendVessels.mockResolvedValue(recResult);
    a.spotVsContract.mockResolvedValue(stratResult);
    a.alternativePort.mockResolvedValue(null);
    a.fixWait.mockResolvedValue({ decision: "FIX_NOW", expected_move_pct: -0.02, effective_confidence: 0.72, drivers: {}, reason: "Rates stable." });

    renderWithRouter(<CharteringPage />);
    await userEvent.click(screen.getByRole("button", { name: /Get recommendation/i }));

    await waitFor(() => expect(screen.getByLabelText("Recommendation")).toBeInTheDocument());
    // Decision verb from fix/wait.
    expect(screen.getByText("FIX NOW")).toBeInTheDocument();
    // Ranked vessel present.
    expect(screen.getByText("Cape One")).toBeInTheDocument();
    // Recommended strategy highlighted.
    expect(screen.getAllByText(/Multi Voyage/i).length).toBeGreaterThan(0);
    expect(screen.getByText("Recommended")).toBeInTheDocument();
  });

  it("shows an error state when the recommendation call fails", async () => {
    a.recommendVessels.mockRejectedValue(new ApiError("http", "Bad request.", { status: 400 }));
    a.spotVsContract.mockResolvedValue(stratResult);
    a.alternativePort.mockResolvedValue(null);

    renderWithRouter(<CharteringPage />);
    await userEvent.click(screen.getByRole("button", { name: /Get recommendation/i }));
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(screen.getByText(/Bad request/i)).toBeInTheDocument();
  });
});
