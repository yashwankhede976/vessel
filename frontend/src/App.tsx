import { useRoutes } from "react-router-dom";
import { routes } from "./routes";

/**
 * Root application component. Renders the route table (which mounts the
 * AppLayout shell and its pages). No API data is fetched in this shell.
 */
export default function App() {
  return useRoutes(routes);
}
