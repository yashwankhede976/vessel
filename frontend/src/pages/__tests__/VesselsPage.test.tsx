import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithRouter, paginated } from "../../test/utils";
import VesselsPage from "../VesselsPage";
import { api } from "../../api";
import type { Vessel } from "../../api";

vi.mock("../../api", async () => {
  const actual = await vi.importActual<typeof import("../../api")>("../../api");
  return {
    ...actual,
    api: { vessels: { list: vi.fn() } },
  };
});

const listMock = api.vessels.list as unknown as ReturnType<typeof vi.fn>;

const vessel = (over: Partial<Vessel> = {}): Vessel => ({
  id: 1, imo: "1000001", mmsi: "123456789", name: "Cape One",
  vessel_type: "capesize", vessel_type_display: "Capesize",
  dwt: "180000.00", loa: "292.00", beam: "45.00", draft: "18.10",
  flag: "PA", year_built: 2015, speed: "13.00",
  availability_status: "open", availability_status_display: "Open / available",
  open_date: null, metadata: {}, latest_position: null, created_at: "", updated_at: "", ...over,
});

describe("VesselsPage", () => {
  beforeEach(() => listMock.mockReset());

  it("shows a loading state then renders vessels", async () => {
    listMock.mockResolvedValue(paginated([vessel(), vessel({ id: 2, name: "Pana Two", vessel_type: "panamax", vessel_type_display: "Panamax" })]));
    renderWithRouter(<VesselsPage />);
    // Table shows a loading status initially.
    expect(screen.getByRole("status")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Cape One")).toBeInTheDocument());
    expect(screen.getByText("Pana Two")).toBeInTheDocument();
  });

  it("shows an empty state when no vessels match", async () => {
    listMock.mockResolvedValue(paginated<Vessel>([]));
    renderWithRouter(<VesselsPage />);
    await waitFor(() =>
      expect(screen.getByText(/No vessels match these filters/i)).toBeInTheDocument(),
    );
  });

  it("opens a detail modal when a vessel name is clicked", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    listMock.mockResolvedValue(paginated([vessel()]));
    renderWithRouter(<VesselsPage />);
    await waitFor(() => expect(screen.getByText("Cape One")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "Cape One" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("1000001")).toBeInTheDocument(); // IMO in modal
  });
});
