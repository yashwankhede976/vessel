/** Recommendations API.
 *
 * Backend endpoints are scaffolded but not yet implemented; paths follow the
 * documented convention.
 */
import { get, getList } from "../client";
import type { ListParams, Paginated } from "../types";
import type { Recommendation } from "../resources";

export interface RecommendationListParams extends ListParams {
  rec_type?: string;
  cargo_requirement?: number;
  route?: number;
}

export const recommendationsApi = {
  list(
    params?: RecommendationListParams,
    signal?: AbortSignal,
  ): Promise<Paginated<Recommendation>> {
    return getList<Recommendation>("recommendations/", { params, signal });
  },
  retrieve(id: number, signal?: AbortSignal): Promise<Recommendation> {
    return get<Recommendation>(`recommendations/${id}/`, { signal });
  },
};
