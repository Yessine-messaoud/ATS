import { requireUser } from "@/lib/session";

/** The candidate's own space: candidates only (recruiters and admins go back to their workspace). */
export default async function CandidateLayout({ children }: LayoutProps<"/me">) {
  await requireUser(["candidate"], "/me");
  return children;
}
