import type { ReactElement } from "react";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { Paginated, Pagination } from "../api";

/** Render a component wrapped in a MemoryRouter at an optional initial path. */
export function renderWithRouter(ui: ReactElement, initialPath = "/") {
  return render(<MemoryRouter initialEntries={[initialPath]}>{ui}</MemoryRouter>);
}

/** Build a Paginated<T> envelope result as the api client would return. */
export function paginated<T>(items: T[]): Paginated<T> {
  const pagination: Pagination = {
    count: items.length,
    page: 1,
    page_size: items.length || 25,
    num_pages: 1,
    next: null,
    previous: null,
  };
  return { items, pagination };
}
