import { api } from "@/lib/api";

import { WeightsForm } from "./weights-form";

export default async function WeightsPage(props: PageProps<"/jobs/[id]/weights">) {
  const { id } = await props.params;
  const ranking = await api.ranking(id, true);
  return <WeightsForm jobId={id} initial={ranking.weights} />;
}
