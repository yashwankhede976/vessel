/** Alerts API — the real /api/v1/alerts/ ViewSet.
 *
 * List/retrieve are GETs; acknowledge/resolve are POSTs (non-idempotent, not
 * retried). Filter by status/alert_type/severity.
 */
import { get, getList, post } from "../client";
import type { ListParams, Paginated } from "../types";
import type { DecisionAlert } from "../resources";

export interface AlertListParams extends ListParams {
  status?: "new" | "acknowledged" | "resolved";
  alert_type?: string;
  severity?: string;
}

export const alertsApi = {
  list(params?: AlertListParams, signal?: AbortSignal): Promise<Paginated<DecisionAlert>> {
    return getList<DecisionAlert>("alerts/", { params, signal });
  },
  retrieve(id: number, signal?: AbortSignal): Promise<DecisionAlert> {
    return get<DecisionAlert>(`alerts/${id}/`, { signal });
  },
  acknowledge(id: number): Promise<DecisionAlert> {
    return post<DecisionAlert>(`alerts/${id}/acknowledge/`);
  },
  resolve(id: number): Promise<DecisionAlert> {
    return post<DecisionAlert>(`alerts/${id}/resolve/`);
  },
};
