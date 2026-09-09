/**
 * React hooks for consuming the API with typed loading/error/data states.
 *
 * `useApi` runs a fetcher on mount (and when its dependency key changes),
 * handling cancellation via AbortController and normalizing errors to ApiError.
 * UI components import this rather than calling the client directly.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "./errors";

export interface ApiState<T> {
  data: T | null;
  loading: boolean;
  error: ApiError | null;
  /** Re-run the fetcher. */
  refetch: () => void;
}

/**
 * Run an async fetcher and track its state. The fetcher receives an
 * AbortSignal so in-flight requests are cancelled on unmount/refetch.
 *
 * @param fetcher  async function performing the request
 * @param deps     dependency list; the fetcher re-runs when these change
 */
export function useApi<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  deps: ReadonlyArray<unknown> = [],
): ApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [nonce, setNonce] = useState(0);

  // Keep the latest fetcher without forcing it into the dependency array.
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const refetch = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    setLoading(true);
    setError(null);

    fetcherRef
      .current(controller.signal)
      .then((result) => {
        if (active) {
          setData(result);
          setLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (!active) return;
        // Ignore cancellations triggered by unmount/refetch.
        if (err instanceof ApiError && err.kind === "aborted") return;
        setError(
          err instanceof ApiError ? err : new ApiError("network", "Unexpected error."),
        );
        setLoading(false);
      });

    return () => {
      active = false;
      controller.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce]);

  return { data, loading, error, refetch };
}
