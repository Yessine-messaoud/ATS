import { AppShell } from "@/components/app-shell";
import { requireUser } from "@/lib/session";

/** Recruiters and platform admins only; candidates are sent to their portal, visitors to sign in. */
export default async function StaffLayout({ children }: LayoutProps<"/">) {
  const user = await requireUser(["recruiter", "admin"]);
  return <AppShell user={user}>{children}</AppShell>;
}
