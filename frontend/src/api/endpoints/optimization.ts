/** Optimization runs & results API.
 *
 * Backend endpoints are scaffolded but not yet implemented; paths follow the
 * documented convention. Triggering a run is a POST (non-idempotent, not
 * retried by the client).
 */
import { get, getList, post } from "../client";
import type { ListParams, Paginated } from "../types";
import type { OptimizationResult, OptimizationRun } from "../resources";

export interface OptimizationRunListParams extends ListParams {
  run_type?: string;
  status?: string;
  cargo_requirement?: number;
}

export interface OptimizationRunInput {
  run_type: string;
  cargo_requirement?: number | null;
  scenario?: number | null;
  parameters?: Record<string, unknown>;
}

export const optimizationApi = {
  listRuns(
    params?: OptimizationRunListParams,
    signal?: AbortSignal,
  ): Promise<Paginated<OptimizationRun>> {
    return getList<OptimizationRun>("optimization/runs/", { params, signal });
  },
  retrieveRun(id: number, signal?: AbortSignal): Promise<OptimizationRun> {
    return get<OptimizationRun>(`optimization/runs/${id}/`, { signal });
  },
  createRun(input: OptimizationRunInput): Promise<OptimizationRun> {
    return post<OptimizationRun>("optimization/runs/", input);
  },
  results(runId: number, signal?: AbortSignal): Promise<Paginated<OptimizationResult>> {
    return getList<OptimizationResult>(`optimization/runs/${runId}/results/`, { signal });
  },
};
