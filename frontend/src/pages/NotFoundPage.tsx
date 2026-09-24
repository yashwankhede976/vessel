import { Link } from "react-router-dom";
import PageHeader from "../components/layout/PageHeader";
import { Card, EmptyState } from "../components/ui";

export default function NotFoundPage() {
  return (
    <>
      <PageHeader title="Page not found" description="The page you requested does not exist." />
      <Card>
        <EmptyState
          icon="⚓"
          title="404 — Off the chart"
          message="The page you requested could not be found. It may have moved or never existed."
          action={
            <Link className="btn btn--primary" to="/dashboard">
              Return to dashboard <span className="btn__arrow" aria-hidden="true">→</span>
            </Link>
          }
        />
      </Card>
    </>
  );
}
