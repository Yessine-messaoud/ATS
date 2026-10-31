import Link from "next/link";
import { BadgeCheck, Scale, ShieldCheck } from "lucide-react";

import { BrandMark } from "@/components/brand";
import { ThemeSwitcher } from "@/components/theme";

const POINTS = [
  { icon: BadgeCheck, title: "Evidence-based profiles", text: "Every skill read from a CV is checked against the document." },
  { icon: Scale, title: "Explainable matching", text: "Deterministic scores you can trace, factor by factor." },
  { icon: ShieldCheck, title: "People decide", text: "The AI suggests; recruiters make every decision, on the record." },
];

export default function AuthLayout({ children }: LayoutProps<"/">) {
  return (
    <div className="grid min-h-screen lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
      <aside className="relative hidden overflow-hidden bg-navy-950 p-10 text-white lg:flex lg:flex-col">
        <div className="pointer-events-none absolute -right-24 -top-24 size-96 rounded-full bg-brand-600/30 blur-3xl" aria-hidden />
        <div className="pointer-events-none absolute -bottom-32 -left-16 size-96 rounded-full bg-lavender-600/20 blur-3xl" aria-hidden />
        <BrandMark />
        <div className="relative mt-auto max-w-md space-y-8">
          <h2 className="text-3xl font-semibold leading-tight tracking-tight">
            Recruitment with AI support, <span className="text-brand-300">and people in charge.</span>
          </h2>
          <ul className="space-y-5">
            {POINTS.map(({ icon: Icon, title, text }) => (
              <li key={title} className="flex gap-3">
                <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-white/10">
                  <Icon className="size-[18px] text-brand-200" aria-hidden />
                </span>
                <span>
                  <span className="block text-sm font-medium">{title}</span>
                  <span className="block text-sm text-slate-400">{text}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
        <p className="relative mt-10 text-xs text-slate-500">
          <Link href="/careers" className="hover:text-slate-300">Browse open jobs</Link> ·{" "}
          <Link href="/privacy" className="hover:text-slate-300">Privacy notice</Link>
        </p>
      </aside>
      <main className="flex flex-col px-4 py-6 sm:px-8">
        <div className="flex items-center justify-between">
          <span className="lg:hidden">
            <BrandMark tone="dark" />
          </span>
          <ThemeSwitcher className="ml-auto" />
        </div>
        <div className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center py-10">{children}</div>
      </main>
    </div>
  );
}
