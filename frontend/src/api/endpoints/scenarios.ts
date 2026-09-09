/** Scenarios (what-if) API.
 *
 * Backend endpoints are scaffolded but not yet implemented; paths follow the
 * documented convention.
 */
import { del, get, getList, patch, post } from "../client";
import type { ListParams, Paginated } from "../types";
import type { Scenario } from "../resources";

export interface ScenarioListParams extends ListParams {
  cargo_requirement?: number;
  is_baseline?: boolean;
}

export interface ScenarioInput {
  name: string;
  description?: string;
  cargo_requirement?: number | null;
  is_baseline?: boolean;
  parameters?: Record<string, unknown>;
}

export const scenariosApi = {
  list(params?: ScenarioListParams, signal?: AbortSignal): Promise<Paginated<Scenario>> {
    return getList<Scenario>("scenarios/", { params, signal });
  },
  retrieve(id: number, signal?: AbortSignal): Promise<Scenario> {
    return get<Scenario>(`scenarios/${id}/`, { signal });
  },
  create(input: ScenarioInput): Promise<Scenario> {
    return post<Scenario>("scenarios/", input);
  },
  update(id: number, input: Partial<ScenarioInput>): Promise<Scenario> {
    return patch<Scenario>(`scenarios/${id}/`, input);
  },
  remove(id: number): Promise<void> {
    return del(`scenarios/${id}/`);
  },
};
