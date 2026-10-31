"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, useTransition, type ReactNode } from "react";
import {
  Activity,
  Bell,
  BarChart3,
  Briefcase,
  Building2,
  Clock,
  Gauge,
  LogOut,
  UserRound,
  ClipboardCheck,
  FileCheck2,
  FileText,
  KanbanSquare,
  LayoutDashboard,
  Loader2,
  Menu as MenuIcon,
  MessageSquare,
  Search,
  Settings,
  ShieldAlert,
  ShieldCheck,
  TriangleAlert,
  Users,
  X,
} from "lucide-react";

import { signOut } from "@/app/(auth)/actions";
import { getNotifications } from "@/app/actions";
import type { User } from "@/lib/api";
import { initials } from "@/lib/format";
import type { Task } from "@/lib/insights";

import { BrandMark } from "./brand";
import { CommandPalette } from "./command-palette";
import { Menu } from "./interactive";
import { ThemeSwitcher } from "./theme";
import { Kbd, cx, focusRing } from "./ui";

type NavItem = { href: string; label: string; icon: typeof LayoutDashboard };

const RECRUITER_NAV: NavItem[] = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/jobs", label: "Jobs", icon: Briefcase },
  { href: "/candidates", label: "Candidates", icon: Users },
  { href: "/assistant", label: "AI Assistant", icon: MessageSquare },
  { href: "/evaluations", label: "CV Evaluation", icon: FileCheck2 },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/audit", label: "Activity Log", icon: Activity },
  { href: "/company", label: "Company", icon: Building2 },
  { href: "/settings", label: "Settings", icon: Settings },
];

const ADMIN_NAV: NavItem[] = [
  { href: "/admin", label: "Overview", icon: Gauge },
  { href: "/admin/companies", label: "Companies", icon: Building2 },
  { href: "/admin/users", label: "Users", icon: Users },
  { href: "/audit", label: "Audit Log", icon: ShieldCheck },
  { href: "/settings", label: "Settings", icon: Settings },
];

function isActive(pathname: string, href: string): boolean {
  if (href === "/" || href === "/admin") return pathname === href;
  if (href === "/evaluations") return pathname.startsWith("/evaluations") || pathname.startsWith("/matches");
  return pathname === href || pathname.startsWith(`${href}/`);
}

function SidebarNav({ nav, pathname, onNavigate }: { nav: NavItem[]; pathname: string; onNavigate?: () => void }) {
  return (
    <nav aria-label="Main">
      <ul className="space-y-0.5">
        {nav.map(({ href, label, icon: Icon }) => {
          const active = isActive(pathname, href);
          return (
            <li key={href}>
              <Link
                href={href}
                onClick={onNavigate}
                aria-current={active ? "page" : undefined}
                className={cx(
                  "relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                  active ? "bg-brand-600/20 font-medium text-white" : "text-slate-400 hover:bg-white/5 hover:text-slate-100",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400",
                )}
              >
                {active && <span className="absolute inset-y-1.5 left-0 w-0.5 rounded-full bg-brand-400" aria-hidden />}
                <Icon className={cx("size-[18px]", active ? "text-brand-300" : "")} aria-hidden />
                {label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

function subtitle(user: User): string {
  return user.role === "admin" ? "Platform administrator" : (user.organization?.name ?? "Recruiter");
}

function UserCard({ user }: { user: User }) {
  return (
    <Link href="/profile" className="flex items-center gap-3 rounded-lg bg-white/5 p-2.5 hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400">
      <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-brand-500/30 text-xs font-semibold text-brand-100">{initials(user.full_name)}</span>
      <div className="min-w-0 text-xs">
        <p className="truncate font-medium text-white">{user.full_name}</p>
        <p className="truncate text-slate-400">{subtitle(user)}</p>
      </div>
    </Link>
  );
}

function Sidebar({ user, pathname, onNavigate }: { user: User; pathname: string; onNavigate?: () => void }) {
  const admin = user.role === "admin";
  return (
    <div className="flex h-full flex-col bg-navy-950 px-3 py-5">
      <div className="px-2">
        <BrandMark href={admin ? "/admin" : "/"} />
      </div>
      {admin && <p className="mt-6 px-3 text-[11px] font-semibold uppercase tracking-wider text-slate-500">Administration</p>}
      <div className={cx("flex-1 overflow-y-auto", admin ? "mt-2" : "mt-8")}>
        <SidebarNav nav={admin ? ADMIN_NAV : RECRUITER_NAV} pathname={pathname} onNavigate={onNavigate} />
      </div>
      <p className="mb-3 px-2 text-[11px] leading-relaxed text-slate-500">Decision support: every decision is made by a recruiter.</p>
      <UserCard user={user} />
    </div>
  );
}

const TASK_ICONS: Record<Task["kind"], ReactNode> = {
  validate: <ClipboardCheck className="text-amber-500" />,
  security: <ShieldAlert className="text-red-500" />,
  verify: <TriangleAlert className="text-amber-500" />,
  screen: <KanbanSquare className="text-brand-500" />,
};

function Notifications() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<Task[] | null>(null);
  const [loading, startLoading] = useTransition();
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (event: MouseEvent) => !root.current?.contains(event.target as Node) && setOpen(false);
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (next) startLoading(async () => setItems(await getNotifications()));
  };

  return (
    <div className="relative" ref={root}>
      <button
        type="button"
        onClick={toggle}
        aria-expanded={open}
        aria-label="Notifications"
        className={cx("relative flex size-9 items-center justify-center rounded-lg text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900 dark:hover:bg-zinc-800 dark:hover:text-zinc-100", focusRing)}
      >
        <Bell className="size-4" />
        {items && items.length > 0 && <span className="absolute right-2 top-2 size-2 rounded-full bg-red-500 ring-2 ring-white dark:ring-zinc-900" />}
      </button>
      {open && (
        <>
          <div role="dialog" aria-label="Notifications" className="absolute right-0 z-40 mt-2 w-[22rem] max-w-[calc(100vw-2rem)] overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-xl dark:border-zinc-800 dark:bg-zinc-900">
            <div className="flex items-center justify-between border-b border-zinc-100 px-4 py-3 dark:border-zinc-800">
              <p className="text-sm font-semibold">Notifications</p>
              {items && <span className="text-xs text-zinc-500">{items.length} to review</span>}
            </div>
            <div className="max-h-96 overflow-y-auto">
              {loading && !items ? (
                <p className="flex items-center justify-center gap-2 py-8 text-sm text-zinc-500">
                  <Loader2 className="size-4 animate-spin" /> Loading…
                </p>
              ) : items && items.length === 0 ? (
                <p className="py-8 text-center text-sm text-zinc-500">You are all caught up.</p>
              ) : (
                <ul className="divide-y divide-zinc-100 dark:divide-zinc-800">
                  {(items ?? []).map((task) => (
                    <li key={task.key}>
                      <Link href={task.href} onClick={() => setOpen(false)} className="flex gap-3 px-4 py-3 hover:bg-zinc-50 dark:hover:bg-zinc-800/60">
                        <span className="mt-0.5 [&>svg]:size-4">{TASK_ICONS[task.kind]}</span>
                        <span className="min-w-0">
                          <span className="block text-sm font-medium">{task.title}</span>
                          <span className="block text-xs text-zinc-500">{task.detail}</span>
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function ProfileMenu({ user }: { user: User }) {
  const [, startTransition] = useTransition();
  return (
    <Menu
      label="Account"
      header={
        <div className="text-xs">
          <p className="font-medium text-zinc-900 dark:text-zinc-100">{user.full_name}</p>
          <p className="truncate text-zinc-500">{user.email}</p>
          <p className="mt-0.5 text-zinc-500">{subtitle(user)}</p>
        </div>
      }
      trigger={<span className="flex size-9 items-center justify-center rounded-full bg-brand-600 text-xs font-semibold text-white">{initials(user.full_name)}</span>}
      items={[
        { label: "My profile", href: "/profile", icon: <UserRound /> },
        ...(user.role === "recruiter" ? [{ label: "Company", href: "/company", icon: <Building2 /> }] : []),
        { label: "Settings", href: "/settings", icon: <Settings /> },
        { label: "Candidate notice", href: "/privacy", icon: <FileText /> },
        { label: "Sign out", icon: <LogOut />, onSelect: () => startTransition(() => signOut()) },
      ]}
    />
  );
}

function PendingBanner() {
  return (
    <div className="flex items-center gap-2 border-b border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-900 sm:px-6 lg:px-8 dark:border-amber-900/60 dark:bg-amber-950/40 dark:text-amber-200">
      <Clock className="size-3.5 shrink-0" aria-hidden />
      Your company is awaiting approval by a platform administrator. You can prepare jobs now; they appear on the job board once approved.
    </div>
  );
}

/** Navy sidebar (desktop) or drawer (mobile), top bar with search, notifications, theme and profile. */
export function AppShell({ user, children }: { user: User; children: ReactNode }) {
  const pathname = usePathname();
  const [drawer, setDrawer] = useState(false);
  const [palette, setPalette] = useState(false);

  return (
    <>
      <a href="#content" className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2 focus:shadow">
        Skip to content
      </a>

      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 lg:block">
        <Sidebar user={user} pathname={pathname} />
      </aside>

      {drawer && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Menu">
          <div className="absolute inset-0 bg-navy-950/60" onClick={() => setDrawer(false)} />
          <div className="absolute inset-y-0 left-0 w-72 max-w-[85vw] shadow-2xl">
            <button
              type="button"
              onClick={() => setDrawer(false)}
              className="absolute right-3 top-5 z-10 rounded-md p-1.5 text-slate-400 hover:bg-white/10 hover:text-white"
              aria-label="Close menu"
            >
              <X className="size-5" />
            </button>
            <Sidebar user={user} pathname={pathname} onNavigate={() => setDrawer(false)} />
          </div>
        </div>
      )}

      <CommandPalette open={palette} onOpenChange={setPalette} />

      <div className="lg:pl-60">
        <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-zinc-200/80 bg-white/85 px-4 backdrop-blur-md dark:border-zinc-800 dark:bg-zinc-950/85 sm:px-6 lg:px-8">
          <button
            type="button"
            onClick={() => setDrawer(true)}
            className={cx("rounded-md p-2 text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800 lg:hidden", focusRing)}
            aria-label="Open menu"
          >
            <MenuIcon className="size-5" />
          </button>
          <button
            type="button"
            onClick={() => setPalette(true)}
            className={cx(
              "flex h-10 min-w-0 flex-1 items-center gap-2 rounded-lg border border-zinc-200 bg-zinc-50 px-3 text-sm text-zinc-500 transition-colors hover:border-zinc-300 hover:bg-white sm:max-w-md dark:border-zinc-800 dark:bg-zinc-900 dark:hover:bg-zinc-800",
              focusRing,
            )}
          >
            <Search className="size-4" aria-hidden />
            <span className="flex-1 truncate text-left">Search jobs, candidates, skills…</span>
            <span className="hidden sm:inline">
              <Kbd>Ctrl K</Kbd>
            </span>
          </button>
          <div className="ml-auto flex shrink-0 items-center gap-0.5 sm:gap-1">
            {user.role === "recruiter" && <Notifications />}
            <ThemeSwitcher />
            <span className="mx-1 hidden h-6 w-px bg-zinc-200 sm:block dark:bg-zinc-800" aria-hidden />
            <ProfileMenu user={user} />
          </div>
        </header>
        {user.organization?.status === "pending" && <PendingBanner />}
        <main id="content">
          <div className="mx-auto max-w-[90rem] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">{children}</div>
        </main>
      </div>
    </>
  );
}
