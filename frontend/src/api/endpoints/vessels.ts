/** Vessels API. */
import { get, getList } from "../client";
import type { ListParams, Paginated } from "../types";
import type { Vessel, VesselAvailabilitySummary } from "../resources";

export interface VesselListParams extends ListParams {
  vessel_type?: string;
  dwt_min?: number;
  dwt_max?: number;
  draft_min?: number;
  draft_max?: number;
  availability_status?: string;
  open_before?: string;
  open_after?: string;
  min_lat?: number;
  max_lat?: number;
  min_lon?: number;
  max_lon?: number;
}

export const vesselsApi = {
  list(params?: VesselListParams, signal?: AbortSignal): Promise<Paginated<Vessel>> {
    return getList<Vessel>("vessels/", { params, signal });
  },
  retrieve(id: number, signal?: AbortSignal): Promise<Vessel> {
    return get<Vessel>(`vessels/${id}/`, { signal });
  },
  available(params?: VesselListParams, signal?: AbortSignal): Promise<Paginated<Vessel>> {
    return getList<Vessel>("vessels/available/", { params, signal });
  },
  /** Fleet availability broken down by vessel type (real DB aggregation). */
  availabilitySummary(
    params?: VesselListParams,
    signal?: AbortSignal,
  ): Promise<VesselAvailabilitySummary> {
    return get<VesselAvailabilitySummary>("vessels/availability-summary/", { params, signal });
  },
};
