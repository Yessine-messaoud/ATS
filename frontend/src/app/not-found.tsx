import { SearchX } from "lucide-react";

import { ButtonLink, Card, Empty } from "@/components/ui";

export default function NotFound() {
  return (
    <Card>
      <Empty icon={<SearchX />} title="This page does not exist" action={<ButtonLink href="/">Back to the dashboard</ButtonLink>}>
        The record may have been erased or merged, or the link is wrong.
      </Empty>
    </Card>
  );
}
