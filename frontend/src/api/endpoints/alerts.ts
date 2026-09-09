/** Alerts API.
 *
 * Backend endpoints are scaffolded but not yet implemented; paths follow the
 * documented convention. Acknowledge is a POST (non-idempotent, not retried).
 */
import { get, getList, post } from "../client";
import type { ListParams, Paginated } from "../types";
import type { Alert } from "../resources";

export interface AlertListParams extends ListParams {
  severity?: string;
  acknowledged?: boolean;
  alert_type?: string;
}

export const alertsApi = {
  list(params?: AlertListParams, signal?: AbortSignal): Promise<Paginated<Alert>> {
    return getList<Alert>("alerts/", { params, signal });
  },
  retrieve(id: number, signal?: AbortSignal): Promise<Alert> {
    return get<Alert>(`alerts/${id}/`, { signal });
  },
  acknowledge(id: number): Promise<Alert> {
    return post<Alert>(`alerts/${id}/acknowledge/`);
  },
};
