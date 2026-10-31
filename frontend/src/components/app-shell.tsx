"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";
import { Briefcase, FileText, LayoutDashboard, Menu, MessageSquare, Search, ShieldCheck, Users, X } from "lucide-react";

import { CommandPalette } from "./command-palette";
import { Toaster } from "./toaster";
import { Kbd, cx, focusRing } from "./ui";

const NAV = [
  {
    label: "Recruiting",
    items: [
      { href: "/", label: "Dashboard", icon: LayoutDashboard },
      { href: "/jobs", label: "Jobs", icon: Briefcase },
      { href: "/candidates", label: "Candidates", icon: Users },
      { href: "/assistant", label: "Assistant", icon: MessageSquare },
    ],
  },
  {
    label: "Governance",
    items: [
      { href: "/audit", label: "Audit log", icon: ShieldCheck },
      { href: "/privacy", label: "Candidate notice", icon: FileText },
    ],
  },
];

function isActive(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

function Logo() {
  return (
    <Link href="/" className={cx("flex items-center gap-2 rounded-md font-semibold tracking-tight", focusRing)}>
      <span className="flex size-7 items-center justify-center rounded-lg bg-indigo-600 text-xs font-bold text-white">AT</span>
      <span>Talent ATS</span>
    </Link>
  );
}

function NavLinks({ pathname, onNavigate }: { pathname: string; onNavigate?: () => void }) {
  return (
    <nav aria-label="Main" className="space-y-5">
      {NAV.map((section) => (
        <div key={section.label}>
          <p className="mb-1 px-2 text-[11px] font-semibold uppercase tracking-wide text-zinc-400">{section.label}</p>
          <ul className="space-y-0.5">
            {section.items.map(({ href, label, icon: Icon }) => {
              const active = isActive(pathname, href);
              return (
                <li key={href}>
                  <Link
                    href={href}
                    onClick={onNavigate}
                    aria-current={active ? "page" : undefined}
                    className={cx(
                      "flex items-center gap-2.5 rounded-md px-2 py-1.5 text-sm transition-colors",
                      active
                        ? "bg-indigo-50 font-medium text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300"
                        : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-100",
                      focusRing,
                    )}
                  >
                    <Icon className="size-4" aria-hidden />
                    {label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}

function SearchButton({ onClick, compact }: { onClick: () => void; compact?: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cx(
        "flex items-center gap-2 rounded-md border border-zinc-200 bg-white text-sm text-zinc-500 shadow-sm hover:border-zinc-300 dark:border-zinc-800 dark:bg-zinc-900",
        compact ? "size-9 justify-center" : "w-full px-2.5 py-1.5",
        focusRing,
      )}
      aria-label="Search"
    >
      <Search className="size-4" aria-hidden />
      {!compact && (
        <>
          <span className="flex-1 text-left">Search…</span>
          <Kbd>Ctrl K</Kbd>
        </>
      )}
    </button>
  );
}

/** Sidebar navigation (desktop), top bar and drawer (mobile), command palette and toasts. */
export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [drawer, setDrawer] = useState(false);
  const [palette, setPalette] = useState(false);


  return (
    <Toaster>
      <a href="#content" className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2 focus:shadow">
        Skip to content
      </a>

      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r border-zinc-200 bg-white px-3 py-4 dark:border-zinc-800 dark:bg-zinc-900 lg:flex">
        <div className="px-2">
          <Logo />
        </div>
        <div className="mt-5">
          <SearchButton onClick={() => setPalette(true)} />
        </div>
        <div className="mt-5 flex-1 overflow-y-auto">
          <NavLinks pathname={pathname} />
        </div>
        <p className="border-t border-zinc-200 px-2 pt-3 text-xs text-zinc-500 dark:border-zinc-800">
          Decision support: every decision is made by a recruiter.
        </p>
      </aside>

      <header className="sticky top-0 z-30 flex h-14 items-center gap-2 border-b border-zinc-200 bg-white/90 px-4 backdrop-blur dark:border-zinc-800 dark:bg-zinc-900/90 lg:hidden">
        <button
          type="button"
          onClick={() => setDrawer(true)}
          className={cx("rounded-md p-2 text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800", focusRing)}
          aria-label="Open menu"
        >
          <Menu className="size-5" />
        </button>
        <Logo />
        <div className="ml-auto">
          <SearchButton compact onClick={() => setPalette(true)} />
        </div>
      </header>

      {drawer && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Menu">
          <div className="absolute inset-0 bg-zinc-950/40" onClick={() => setDrawer(false)} />
          <div className="absolute inset-y-0 left-0 flex w-72 max-w-[85vw] flex-col bg-white px-3 py-4 shadow-xl dark:bg-zinc-900">
            <div className="flex items-center justify-between px-2">
              <Logo />
              <button
                type="button"
                onClick={() => setDrawer(false)}
                className={cx("rounded-md p-2 text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800", focusRing)}
                aria-label="Close menu"
              >
                <X className="size-5" />
              </button>
            </div>
            <div className="mt-5 flex-1 overflow-y-auto">
              <NavLinks pathname={pathname} onNavigate={() => setDrawer(false)} />
            </div>
          </div>
        </div>
      )}

      <CommandPalette open={palette} onOpenChange={setPalette} />

      <main id="content" className="lg:pl-60">
        <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">{children}</div>
      </main>
    </Toaster>
  );
}
