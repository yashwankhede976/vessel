import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithRouter } from "../../test/utils";
import ScenariosPage from "../ScenariosPage";
import { api } from "../../api";
import type { RiskResult, VoyageEconomicsResult } from "../../api";

vi.mock("../../api", async () => {
  const actual = await vi.importActual<typeof import("../../api")>("../../api");
  return {
    ...actual,
    api: { analytics: { voyageCost: vi.fn(), risk: vi.fn() } },
  };
});

const a = api.analytics as unknown as {
  voyageCost: ReturnType<typeof vi.fn>;
  risk: ReturnType<typeof vi.fn>;
};

const voyage: VoyageEconomicsResult = {
  currency: "USD", distance_nm: "6500", distance_km: "12038", sailing_days: "20.8",
  port_days: "2.4", total_days: "23.2", cargo_tonnes: "75000", bunker_consumption_tonnes: "936",
  cost_components: { bunker_cost: { amount: "561600", currency: "USD", unit: "total" } },
  total_voyage_cost: { amount: "1922410", currency: "USD", unit: "total" },
  cost_per_tonne: { amount: "25.63", currency: "USD", unit: "per_tonne" },
  cost_per_day: null, cost_per_tonne_km: null, inputs: {},
};
const risk: RiskResult = {
  overall_score: 48, risk_level: "MEDIUM", factors: [], inputs: {}, unknown_factors: [],
};

describe("ScenariosPage", () => {
  beforeEach(() => {
    a.voyageCost.mockReset();
    a.risk.mockReset();
  });

  it("recomputes impact from the levers via backend compute endpoints", async () => {
    a.voyageCost.mockResolvedValue(voyage);
    a.risk.mockResolvedValue(risk);
    renderWithRouter(<ScenariosPage />);
    await userEvent.click(screen.getByRole("button", { name: /Run scenario/i }));
    await waitFor(() => expect(a.voyageCost).toHaveBeenCalled());
    expect(a.risk).toHaveBeenCalled();
    // Impact rendered.
    expect(await screen.findByText("Total voyage cost")).toBeInTheDocument();
    expect(screen.getByText("$1,922,410 /t".replace(" /t", ""))).toBeInTheDocument;
    expect(screen.getByText(/Medium/i)).toBeInTheDocument();
  });

  it("does not call the backend on initial render (stateless what-if)", () => {
    a.voyageCost.mockResolvedValue(voyage);
    a.risk.mockResolvedValue(risk);
    renderWithRouter(<ScenariosPage />);
    expect(a.voyageCost).not.toHaveBeenCalled();
    expect(a.risk).not.toHaveBeenCalled();
  });
});
