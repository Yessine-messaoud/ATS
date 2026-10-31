import { KanbanSquare } from "lucide-react";

import { BlindToggle, isBlind } from "@/components/blind-toggle";
import { ButtonLink, Card, Empty } from "@/components/ui";
import { api } from "@/lib/api";

import { Kanban } from "./kanban";

export default async function PipelinePage(props: PageProps<"/jobs/[id]/pipeline">) {
  const { id } = await props.params;
  const blind = isBlind((await props.searchParams).blind);
  const applications = await api.applications(id, blind);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-zinc-500">
          Drag a card, or use its menu, to change the stage. Every move is recorded as a recruiter decision.
        </p>
        <BlindToggle href={`/jobs/${id}/pipeline`} blind={blind} />
      </div>
      {applications.length === 0 ? (
        <Card>
          <Empty
            icon={<KanbanSquare />}
            title="The pipeline is empty"
            action={<ButtonLink href={`/jobs/${id}`}>Pick candidates from the ranking</ButtonLink>}
          >
            Add candidates from the ranking; they start in the “New” stage.
          </Empty>
        </Card>
      ) : (
        <Kanban applications={applications} blind={blind} />
      )}
    </div>
  );
}
