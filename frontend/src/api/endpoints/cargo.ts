/** Cargo requirements API.
 *
 * Note: the backend cargo endpoints are scaffolded but not yet implemented.
 * These typed functions target the documented paths so UI can integrate as the
 * endpoints land. Paths follow the ports/vessels convention.
 */
import { get, getList } from "../client";
import type { ListParams, Paginated } from "../types";
import type { CargoRequirement } from "../resources";

export interface CargoListParams extends ListParams {
  status?: string;
  commodity?: number;
  destination_port?: number;
}

export const cargoApi = {
  list(params?: CargoListParams, signal?: AbortSignal): Promise<Paginated<CargoRequirement>> {
    return getList<CargoRequirement>("cargo/cargo-requirements/", { params, signal });
  },
  retrieve(id: number, signal?: AbortSignal): Promise<CargoRequirement> {
    return get<CargoRequirement>(`cargo/cargo-requirements/${id}/`, { signal });
  },
};
