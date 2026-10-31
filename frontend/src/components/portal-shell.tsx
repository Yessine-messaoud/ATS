"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useTransition, type ReactNode } from "react";
import { Briefcase, FileText, LayoutDashboard, LogOut, Menu as MenuIcon, Settings, UserRound, X } from "lucide-react";

import { signOut } from "@/app/(auth)/actions";
import type { User } from "@/lib/api";
import { initials } from "@/lib/format";

import { BrandMark } from "./brand";
import { Menu } from "./interactive";
import { ThemeSwitcher } from "./theme";
import { buttonClass, cx, focusRing } from "./ui";

const CANDIDATE_NAV = [
  { href: "/careers", label: "Find jobs", icon: Briefcase },
  { href: "/me", label: "My applications", icon: LayoutDashboard },
  { href: "/me/profile", label: "My profile", icon: UserRound },
  { href: "/me/settings", label: "Account & privacy", icon: Settings },
];

function active(pathname: string, href: string) {
  return href === "/me" ? pathname === "/me" : pathname === href || pathname.startsWith(`${href}/`);
}

function NavLinks({ user, pathname, onNavigate, vertical }: { user: User | null; pathname: string; onNavigate?: () => void; vertical?: boolean }) {
  const nav = user?.role === "candidate" ? CANDIDATE_NAV : CANDIDATE_NAV.slice(0, 1);
  return (
    <ul className={cx(vertical ? "space-y-1" : "flex items-center gap-1")}>
      {nav.map(({ href, label, icon: Icon }) => (
        <li key={href}>
          <Link
            href={href}
            onClick={onNavigate}
            aria-current={active(pathname, href) ? "page" : undefined}
            className={cx(
              "flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors",
              active(pathname, href)
                ? "bg-brand-50 font-medium text-brand-700 dark:bg-brand-500/15 dark:text-brand-200"
                : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800 dark:hover:text-white",
              focusRing,
            )}
          >
            <Icon className="size-4" aria-hidden />
            {label}
          </Link>
        </li>
      ))}
    </ul>
  );
}

function AccountMenu({ user }: { user: User }) {
  const [, startTransition] = useTransition();
  const staff = user.role !== "candidate";
  return (
    <Menu
      label="Account"
      header={
        <div className="text-xs">
          <p className="font-medium text-zinc-900 dark:text-zinc-100">{user.full_name}</p>
          <p className="truncate text-zinc-500">{user.email}</p>
        </div>
      }
      trigger={<span className="flex size-9 items-center justify-center rounded-full bg-brand-600 text-xs font-semibold text-white">{initials(user.full_name)}</span>}
      items={[
        ...(staff
          ? [{ label: "Back to my workspace", href: user.role === "admin" ? "/admin" : "/", icon: <LayoutDashboard /> }]
          : [
              { label: "My applications", href: "/me", icon: <LayoutDashboard /> },
              { label: "Account & privacy", href: "/me/settings", icon: <Settings /> },
            ]),
        { label: "Privacy notice", href: "/privacy", icon: <FileText /> },
        { label: "Sign out", icon: <LogOut />, onSelect: () => startTransition(() => signOut()) },
      ]}
    />
  );
}

/** Light top-navigation shell for candidates and visitors (no sidebar: fewer, simpler pages). */
export function PortalShell({ user, children }: { user: User | null; children: ReactNode }) {
  const pathname = usePathname();
  const [drawer, setDrawer] = useState(false);
  const next = encodeURIComponent(pathname);

  return (
    <div className="flex min-h-screen flex-col">
      <a href="#content" className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2 focus:shadow">
        Skip to content
      </a>
      <header className="sticky top-0 z-20 border-b border-zinc-200/80 bg-white/85 backdrop-blur-md dark:border-zinc-800 dark:bg-zinc-950/85">
        <div className="mx-auto flex h-16 max-w-6xl items-center gap-4 px-4 sm:px-6">
          <BrandMark href="/careers" tone="dark" />
          <nav aria-label="Main" className="hidden md:block">
            <NavLinks user={user} pathname={pathname} />
          </nav>
          <div className="ml-auto flex items-center gap-1.5">
            <ThemeSwitcher />
            {user ? (
              <AccountMenu user={user} />
            ) : (
              <>
                <Link href={`/login?next=${next}`} className={cx(buttonClass("ghost"), "hidden sm:inline-flex")}>
                  Sign in
                </Link>
                <Link href={`/signup?next=${next}`} className={buttonClass("primary")}>
                  Create account
                </Link>
              </>
            )}
            {user?.role === "candidate" && (
              <button type="button" onClick={() => setDrawer(!drawer)} aria-expanded={drawer} aria-label="Menu" className={cx("rounded-md p-2 text-zinc-600 hover:bg-zinc-100 md:hidden dark:text-zinc-300 dark:hover:bg-zinc-800", focusRing)}>
                {drawer ? <X className="size-5" /> : <MenuIcon className="size-5" />}
              </button>
            )}
          </div>
        </div>
        {drawer && (
          <nav aria-label="Main" className="border-t border-zinc-200 px-4 py-3 md:hidden dark:border-zinc-800">
            <NavLinks user={user} pathname={pathname} onNavigate={() => setDrawer(false)} vertical />
          </nav>
        )}
      </header>
      <main id="content" className="flex-1">
        <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:py-10">{children}</div>
      </main>
      <footer className="border-t border-zinc-200/80 py-6 text-center text-xs text-zinc-500 dark:border-zinc-800">
        RecruitAI · AI supports recruiters; people make every decision ·{" "}
        <Link href="/privacy" className="hover:text-zinc-800 dark:hover:text-zinc-200">
          Privacy notice
        </Link>
        {!user && (
          <>
            {" · "}
            <Link href="/signup?type=company" className="hover:text-zinc-800 dark:hover:text-zinc-200">
              Hiring? Create a company account
            </Link>
          </>
        )}
      </footer>
    </div>
  );
}
