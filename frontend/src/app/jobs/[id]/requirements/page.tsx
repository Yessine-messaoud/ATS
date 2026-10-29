import { api } from "@/lib/api";

import { RequirementsEditor } from "./requirements-editor";

export default async function RequirementsPage(props: PageProps<"/jobs/[id]/requirements">) {
  const { id } = await props.params;
  const job = await api.job(id);
  return <RequirementsEditor jobId={job.id} initial={job.profile} validated={job.requirements_validated} />;
}
