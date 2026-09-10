import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithRouter, paginated } from "../../test/utils";
import AlertsPage from "../AlertsPage";
import { api } from "../../api";
import type { DecisionAlert } from "../../api";

vi.mock("../../api", async () => {
  const actual = await vi.importActual<typeof import("../../api")>("../../api");
  return {
    ...actual,
    api: { alerts: { list: vi.fn(), acknowledge: vi.fn(), resolve: vi.fn() } },
  };
});

const listMock = api.alerts.list as unknown as ReturnType<typeof vi.fn>;
const ackMock = api.alerts.acknowledge as unknown as ReturnType<typeof vi.fn>;
const resolveMock = api.alerts.resolve as unknown as ReturnType<typeof vi.fn>;

const alert = (over: Partial<DecisionAlert> = {}): DecisionAlert => ({
  id: 1, alert_type: "congestion_increase", severity: "high",
  timestamp: "2026-09-01T00:00:00Z", entity: "Paradip", route: null, port: null, vessel: null,
  trigger_value: "80", threshold: "55", message: "Congestion elevated",
  recommended_action: "Assess alternative ports", status: "new",
  acknowledged_at: null, resolved_at: null, context: {}, notifications: [],
  created_at: "", updated_at: "", ...over,
});

describe("AlertsPage", () => {
  beforeEach(() => {
    listMock.mockReset();
    ackMock.mockReset();
    resolveMock.mockReset();
  });

  it("renders alerts with severity and recommended action", async () => {
    listMock.mockResolvedValue(paginated([alert()]));
    renderWithRouter(<AlertsPage />);
    await waitFor(() => expect(screen.getByText("Congestion elevated")).toBeInTheDocument());
    expect(screen.getByText("Assess alternative ports")).toBeInTheDocument();
  });

  it("acknowledges an alert and refetches", async () => {
    listMock.mockResolvedValue(paginated([alert()]));
    ackMock.mockResolvedValue(alert({ status: "acknowledged" }));
    renderWithRouter(<AlertsPage />);
    await waitFor(() => expect(screen.getByText("Congestion elevated")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "Ack" }));
    await waitFor(() => expect(ackMock).toHaveBeenCalledWith(1));
    // list is refetched (called at least twice: initial + after ack).
    expect(listMock.mock.calls.length).toBeGreaterThanOrEqual(2);
  });

  it("resolves an alert", async () => {
    listMock.mockResolvedValue(paginated([alert()]));
    resolveMock.mockResolvedValue(alert({ status: "resolved" }));
    renderWithRouter(<AlertsPage />);
    await waitFor(() => expect(screen.getByText("Congestion elevated")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "Resolve" }));
    await waitFor(() => expect(resolveMock).toHaveBeenCalledWith(1));
  });

  it("filters by client-side search", async () => {
    listMock.mockResolvedValue(paginated([alert(), alert({ id: 2, message: "Cyclone warning", entity: "Bay of Bengal" })]));
    renderWithRouter(<AlertsPage />);
    await waitFor(() => expect(screen.getByText("Congestion elevated")).toBeInTheDocument());
    await userEvent.type(screen.getByPlaceholderText(/message, entity, type/i), "cyclone");
    await waitFor(() => expect(screen.queryByText("Congestion elevated")).not.toBeInTheDocument());
    expect(screen.getByText("Cyclone warning")).toBeInTheDocument();
  });
});
