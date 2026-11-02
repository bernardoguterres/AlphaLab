import { Link, useLocation } from "react-router-dom";
import { Page } from "@/components/layout/Page";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  const { pathname } = useLocation();
  return (
    <Page title="Page not found">
      <p className="text-[13px] text-muted-foreground">
        Nothing lives at <span className="num text-foreground">{pathname}</span>.{" "}
        <Button asChild variant="link">
          <Link to="/">Back to the overview</Link>
        </Button>
        .
      </p>
    </Page>
  );
}
