/** Ports & berths API. */
import { get, getList } from "../client";
import type { ListParams, Paginated } from "../types";
import type { Berth, Port, PortConstraints, PortDetail } from "../resources";

export interface PortListParams extends ListParams {
  coast?: string;
  commodity?: string;
  port_type?: string;
  country?: string;
}

export const portsApi = {
  list(params?: PortListParams, signal?: AbortSignal): Promise<Paginated<Port>> {
    return getList<Port>("ports/", { params, signal });
  },
  retrieve(id: number, signal?: AbortSignal): Promise<PortDetail> {
    return get<PortDetail>(`ports/${id}/`, { signal });
  },
  constraints(id: number, signal?: AbortSignal): Promise<PortConstraints> {
    return get<PortConstraints>(`ports/${id}/constraints/`, { signal });
  },
};

export interface BerthListParams extends ListParams {
  port?: number;
  commodity?: string;
}

export const berthsApi = {
  list(params?: BerthListParams, signal?: AbortSignal): Promise<Paginated<Berth>> {
    return getList<Berth>("ports/berths/", { params, signal });
  },
  retrieve(id: number, signal?: AbortSignal): Promise<Berth> {
    return get<Berth>(`ports/berths/${id}/`, { signal });
  },
};
