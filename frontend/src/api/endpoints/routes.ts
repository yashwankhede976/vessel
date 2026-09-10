/** Routes (trade lanes) API — voyage lines for the map. */
import { getList } from "../client";
import type { ListParams, Paginated } from "../types";
import type { VoyageRoute } from "../resources";

export interface RouteListParams extends ListParams {
  origin?: string;
  destination?: string;
}

export const routesApi = {
  list(params?: RouteListParams, signal?: AbortSignal): Promise<Paginated<VoyageRoute>> {
    return getList<VoyageRoute>("routes/", { params, signal });
  },
};
