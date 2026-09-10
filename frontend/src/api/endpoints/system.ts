/**
 * System / observability API — data freshness and external-service health.
 * Read-only GETs. The external-services endpoint never returns API keys (only a
 * `configured` boolean), so nothing sensitive reaches the client.
 */
import { get } from "../client";
import type { DataFreshnessResponse, ExternalServicesResponse } from "../resources";

export const systemApi = {
  dataFreshness(signal?: AbortSignal): Promise<DataFreshnessResponse> {
    return get<DataFreshnessResponse>("system/data-freshness/", { signal });
  },
  externalServices(signal?: AbortSignal): Promise<ExternalServicesResponse> {
    return get<ExternalServicesResponse>("system/external-services/", { signal });
  },
};
