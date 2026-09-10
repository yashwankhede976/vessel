import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithRouter } from "../../test/utils";
import FreightForecastPage from "../FreightForecastPage";
import { api } from "../../api";
import type { FreightForecastResponse } from "../../api";

vi.mock("../../api", async () => {
  const actual = await vi.importActual<typeof import("../../api")>("../../api");
  return { ...actual, api: { analytics: { freightForecast: vi.fn() } } };
});

const ffMock = api.analytics.freightForecast as unknown as ReturnType<typeof vi.fn>;

const response: FreightForecastResponse = {
  route: { origin: "Australia", destination: "Paradip" },
  historical: [
    { date: "2026-06-01", rate_per_tonne: "18.00", currency: "USD", rate_type: "spot", is_estimated: false, source: "proxy" },
    { date: "2026-06-08", rate_per_tonne: "18.50", currency: "USD", rate_type: "spot", is_estimated: false, source: "proxy" },
  ],
  forecast: [
    { target_date: "2026-06-15", horizon: "short_term", predicted_rate_per_tonne: "19.00", lower_bound: "18.00", upper_bound: "20.00", confidence: "0.80", currency: "USD" },
  ],
  model: { model_name: "freight_gbm_xgboost", model_version: "0.2.0" },
  data_freshness: null, cached: false,
};

describe("FreightForecastPage", () => {
  beforeEach(() => ffMock.mockReset());

  it("loads a lane and renders the forecast chart + points table", async () => {
    ffMock.mockResolvedValue(response);
    renderWithRouter(<FreightForecastPage />);
    await userEvent.click(screen.getByRole("button", { name: /Load forecast/i }));
    await waitFor(() => expect(ffMock).toHaveBeenCalled());
    // SVG chart rendered (role img with aria-label).
    expect(await screen.findByLabelText(/Line chart/i)).toBeInTheDocument();
    // Forecast point row present.
    expect(screen.getByText("2026-06-15")).toBeInTheDocument();
    // FORECAST label present.
    expect(screen.getAllByText("FORECAST").length).toBeGreaterThan(0);
  });

  it("shows a graceful empty state when the lane has no data", async () => {
    ffMock.mockResolvedValue({ ...response, historical: [], forecast: [], route: null, message: "No route found." });
    renderWithRouter(<FreightForecastPage />);
    await userEvent.click(screen.getByRole("button", { name: /Load forecast/i }));
    await waitFor(() => expect(screen.getByText(/No route found/i)).toBeInTheDocument());
  });
});
