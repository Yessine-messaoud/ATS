import { BlindToggle, isBlind } from "@/components/blind-toggle";
import { api } from "@/lib/api";

import { Kanban } from "./kanban";

export default async function PipelinePage(props: PageProps<"/jobs/[id]/pipeline">) {
  const { id } = await props.params;
  const blind = isBlind((await props.searchParams).blind);
  const applications = await api.applications(id, blind);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm text-zinc-500">
          Drag a card or use its menu to change the stage. Every move is recorded as a recruiter decision.
        </p>
        <BlindToggle href={`/jobs/${id}/pipeline`} blind={blind} />
      </div>
      <Kanban applications={applications} blind={blind} />
    </div>
  );
}
