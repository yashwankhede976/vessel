import { Link } from "react-router-dom";
import PageHeader from "../components/layout/PageHeader";
import { Card } from "../components/ui";

export default function NotFoundPage() {
  return (
    <>
      <PageHeader title="Page not found" description="The page you requested does not exist." />
      <Card>
        <p style={{ margin: 0 }}>
          <Link to="/dashboard">Return to the dashboard</Link>
        </p>
      </Card>
    </>
  );
}
