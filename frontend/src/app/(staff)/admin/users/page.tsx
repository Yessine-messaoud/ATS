import type { Metadata } from "next";
import Link from "next/link";
import { Users } from "lucide-react";

import { Avatar } from "@/components/avatar";
import { Badge, Card, Empty, PageHeader, cx, inputClass } from "@/components/ui";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { requireUser } from "@/lib/session";

import { CreateUserButton, UserActions } from "./user-actions";

export const metadata: Metadata = { title: "Users" };

const ROLES = [
  { value: undefined, label: "All" },
  { value: "recruiter", label: "Recruiters" },
  { value: "candidate", label: "Candidates" },
  { value: "admin", label: "Admins" },
] as const;
const ROLE_TONE = { admin: "indigo", recruiter: "blue", candidate: "neutral" } as const;

export default async function UsersPage({ searchParams }: PageProps<"/admin/users">) {
  const admin = await requireUser(["admin"], "/admin/users");
  const params = await searchParams;
  const pick = (key: string) => (typeof params[key] === "string" ? (params[key] as string) : undefined);
  const role = ROLES.find((r) => r.value === pick("role"))?.value;
  const filters = { role, q: pick("q"), organization_id: pick("organization_id") };
  const [users, companies] = await Promise.all([api.adminUsers(filters), api.adminOrganizations()]);
  const company = companies.find((c) => c.id === filters.organization_id);
  const href = (r: string | undefined) => `/admin/users?${new URLSearchParams(Object.entries({ ...filters, role: r }).filter((e): e is [string, string] => !!e[1]))}`;

  return (
    <div className="space-y-6">
      <PageHeader
        crumbs={[{ label: "Administration", href: "/admin" }, { label: "Users" }]}
        title={company ? `Users of ${company.name}` : "Users"}
        description="Every account on the platform. Deactivating an account signs it out everywhere."
        actions={<CreateUserButton companies={companies.filter((c) => c.status !== "suspended")} />}
      />
      <Card flush>
        <div className="flex flex-wrap items-center gap-2 border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
          <nav className="flex flex-wrap gap-1" aria-label="Filter by role">
            {ROLES.map(({ value, label }) => (
              <Link
                key={label}
                href={href(value)}
                aria-current={role === value ? "page" : undefined}
                className={cx(
                  "rounded-md px-3 py-1.5 text-sm",
                  role === value ? "bg-brand-50 font-medium text-brand-700 dark:bg-brand-500/15 dark:text-brand-200" : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800",
                )}
              >
                {label}
              </Link>
            ))}
          </nav>
          <form className="ml-auto flex gap-2" action="/admin/users">
            {role && <input type="hidden" name="role" value={role} />}
            {filters.organization_id && <input type="hidden" name="organization_id" value={filters.organization_id} />}
            <input name="q" defaultValue={filters.q} placeholder="Name or email" aria-label="Search users" className={cx(inputClass, "sm:w-56")} />
          </form>
        </div>
        {users.length === 0 ? (
          <Empty icon={<Users />} title="No account matches" />
        ) : (
          <div className="relative overflow-x-auto">
            <table className="w-full min-w-[52rem] text-sm">
              <thead className="border-b border-zinc-200 bg-zinc-50/80 text-left text-xs text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/60">
                <tr>
                  <th scope="col" className="px-4 py-2.5 font-medium">User</th>
                  <th scope="col" className="px-4 py-2.5 font-medium">Role</th>
                  <th scope="col" className="px-4 py-2.5 font-medium">Company</th>
                  <th scope="col" className="px-4 py-2.5 font-medium">Last sign-in</th>
                  <th scope="col" className="px-4 py-2.5 font-medium">Created</th>
                  <th scope="col" className="px-4 py-2.5"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
                {users.map((user) => (
                  <tr key={user.id} className={user.is_active ? "" : "opacity-60"}>
                    <td className="px-4 py-3">
                      <span className="flex items-center gap-3">
                        <Avatar id={user.id} name={user.full_name} size="sm" />
                        <span className="min-w-0">
                          <span className="block truncate font-medium">
                            {user.full_name}
                            {user.id === admin.id && <span className="ml-1 text-xs font-normal text-zinc-500">(you)</span>}
                          </span>
                          <span className="block truncate text-xs text-zinc-500">{user.email}</span>
                        </span>
                      </span>
                    </td>
                    <td className="space-x-1 px-4 py-3">
                      <Badge tone={ROLE_TONE[user.role]}>{user.role}</Badge>
                      {!user.is_active && <Badge tone="red">deactivated</Badge>}
                    </td>
                    <td className="px-4 py-3 text-zinc-600 dark:text-zinc-300">{user.organization?.name ?? "—"}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-zinc-500">{user.last_login_at ? formatDate(user.last_login_at) : "never"}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-zinc-500">{formatDate(user.created_at)}</td>
                    <td className="px-4 py-3 text-right">{user.id !== admin.id && <UserActions user={user} />}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
