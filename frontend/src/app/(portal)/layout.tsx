import { PortalShell } from "@/components/portal-shell";
import { currentUser } from "@/lib/session";

/** The public job board and the candidate space. Visitors browse freely; applying needs a candidate account. */
export default async function PortalLayout({ children }: LayoutProps<"/">) {
  const user = await currentUser();
  return <PortalShell user={user}>{children}</PortalShell>;
}
