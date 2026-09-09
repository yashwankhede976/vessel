/**
 * Shared API types that mirror the backend response envelope and the DRF
 * conventions (see docs/API_CONVENTIONS.md).
 *
 * Every backend response is one of:
 *   success (single):     { success: true, data: T, errors: null }
 *   success (paginated):  { success: true, data: T[], pagination: {...}, errors: null }
 *   error:                { success: false, data: null, errors: ApiErrorItem[] }
 */

export interface ApiErrorItem {
  code: string;
  detail: string;
  field?: string;
}

export interface Pagination {
  count: number;
  page: number;
  page_size: number;
  num_pages: number;
  next: string | null;
  previous: string | null;
}

export interface SuccessEnvelope<T> {
  success: true;
  data: T;
  errors: null;
  pagination?: Pagination;
}

export interface ErrorEnvelope {
  success: false;
  data: null;
  errors: ApiErrorItem[];
}

export type ApiEnvelope<T> = SuccessEnvelope<T> | ErrorEnvelope;

/** A paginated result surfaced to callers: items plus pagination metadata. */
export interface Paginated<T> {
  items: T[];
  pagination: Pagination | null;
}

/** Common query params for list endpoints (pagination/ordering/search). */
export interface ListParams {
  page?: number;
  page_size?: number;
  ordering?: string;
  search?: string;
  [key: string]: string | number | boolean | undefined;
}
