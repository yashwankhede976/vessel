import type { ReactNode } from "react";
import Loading from "./Loading";
import ErrorState from "./ErrorState";
import "./Table.css";

export interface Column<T> {
  key: string;
  header: ReactNode;
  /** Cell renderer; defaults to (row) => row[key]. */
  render?: (row: T) => ReactNode;
  align?: "left" | "right" | "center";
  width?: string;
}

interface TableProps<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string | number;
  loading?: boolean;
  error?: boolean;
  onRetry?: () => void;
  emptyMessage?: string;
}

/** A generic, typed data table with loading/error/empty states. */
export default function Table<T>({
  columns,
  rows,
  rowKey,
  loading = false,
  error = false,
  onRetry,
  emptyMessage = "No records to display.",
}: TableProps<T>) {
  if (loading) return <Loading fill label="Loading data…" />;
  if (error) return <ErrorState onRetry={onRetry} />;

  return (
    <div className="ui-table__wrap">
      <table className="ui-table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                style={{ textAlign: col.align ?? "left", width: col.width }}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td className="ui-table__empty" colSpan={columns.length}>
                {emptyMessage}
              </td>
            </tr>
          ) : (
            rows.map((row) => (
              <tr key={rowKey(row)}>
                {columns.map((col) => (
                  <td key={col.key} style={{ textAlign: col.align ?? "left" }}>
                    {col.render
                      ? col.render(row)
                      : String((row as Record<string, unknown>)[col.key] ?? "")}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
