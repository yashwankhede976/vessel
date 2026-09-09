/** Freight & ETA forecasts API.
 *
 * Backend endpoints are scaffolded but not yet implemented; paths follow the
 * documented convention.
 */
import { get, getList } from "../client";
import type { ListParams, Paginated } from "../types";
import type { ETAForecast, FreightForecast } from "../resources";

export interface FreightForecastParams extends ListParams {
  route?: number;
  horizon?: "short_term" | "medium_term";
  vessel_type?: string;
}

export interface ETAForecastParams extends ListParams {
  vessel?: number;
  destination_port?: number;
}

export const forecastsApi = {
  freight: {
    list(
      params?: FreightForecastParams,
      signal?: AbortSignal,
    ): Promise<Paginated<FreightForecast>> {
      return getList<FreightForecast>("forecasts/freight-forecasts/", { params, signal });
    },
    retrieve(id: number, signal?: AbortSignal): Promise<FreightForecast> {
      return get<FreightForecast>(`forecasts/freight-forecasts/${id}/`, { signal });
    },
  },
  eta: {
    list(params?: ETAForecastParams, signal?: AbortSignal): Promise<Paginated<ETAForecast>> {
      return getList<ETAForecast>("forecasts/eta-forecasts/", { params, signal });
    },
    retrieve(id: number, signal?: AbortSignal): Promise<ETAForecast> {
      return get<ETAForecast>(`forecasts/eta-forecasts/${id}/`, { signal });
    },
  },
};
