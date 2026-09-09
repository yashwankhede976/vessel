/** Freight observations / historical analytics API.
 *
 * Backend endpoints are scaffolded but not yet implemented; paths follow the
 * documented convention.
 */
import { get, getList } from "../client";
import type { ListParams, Paginated } from "../types";
import type { FreightObservation } from "../resources";

export interface FreightListParams extends ListParams {
  route?: number;
  vessel_type?: string;
  rate_type?: string;
  observed_on?: string;
}

export const freightApi = {
  list(
    params?: FreightListParams,
    signal?: AbortSignal,
  ): Promise<Paginated<FreightObservation>> {
    return getList<FreightObservation>("freight/freight-observations/", { params, signal });
  },
  retrieve(id: number, signal?: AbortSignal): Promise<FreightObservation> {
    return get<FreightObservation>(`freight/freight-observations/${id}/`, { signal });
  },
};
