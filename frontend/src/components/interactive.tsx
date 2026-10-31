"use client";

// Interactive primitives (client components): dropdown menu, modal dialog, slider, pagination, sortable header.
import Link from "next/link";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight, X } from "lucide-react";

import { cx, focusRing } from "./ui";

export type MenuItem =
  | { label: string; href: string; icon?: ReactNode }
  | { label: string; onSelect: () => void; icon?: ReactNode; danger?: boolean; disabled?: boolean };

/** Dropdown menu: opens on click, closes on Escape, outside click or selection; arrow keys move between items. */
export function Menu({
  trigger,
  label,
  items,
  align = "end",
  header,
  className,
}: {
  trigger: ReactNode;
  label: string;
  items: MenuItem[];
  align?: "start" | "end";
  header?: ReactNode;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const list = useRef<HTMLDivElement>(null);
  const id = useId();

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    list.current?.querySelector<HTMLElement>("[role=menuitem]:not([aria-disabled=true])")?.focus();
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  const onKeyDown = (event: React.KeyboardEvent) => {
    const entries = Array.from(list.current?.querySelectorAll<HTMLElement>("[role=menuitem]:not([aria-disabled=true])") ?? []);
    const index = entries.indexOf(document.activeElement as HTMLElement);
    if (event.key === "Escape") {
      setOpen(false);
      root.current?.querySelector<HTMLElement>("button")?.focus();
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      entries[(index + 1) % entries.length]?.focus();
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      entries[(index - 1 + entries.length) % entries.length]?.focus();
    }
  };

  const itemClass = (danger?: boolean) =>
    cx(
      "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm outline-none [&>svg]:size-4",
      danger
        ? "text-red-600 hover:bg-red-50 focus:bg-red-50 dark:text-red-400 dark:hover:bg-red-950/50 dark:focus:bg-red-950/50"
        : "text-zinc-700 hover:bg-zinc-100 focus:bg-zinc-100 dark:text-zinc-200 dark:hover:bg-zinc-800 dark:focus:bg-zinc-800",
    );

  return (
    <div ref={root} className={cx("relative inline-block", className)} onKeyDown={onKeyDown}>
      <button
        type="button"
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen(!open)}
        className={cx("rounded-md", focusRing)}
      >
        {trigger}
      </button>
      {open && (
        <div
          ref={list}
          id={id}
          role="menu"
          aria-label={label}
          className={cx(
            "absolute z-40 mt-1 min-w-48 rounded-lg border border-zinc-200 bg-white p-1 shadow-lg dark:border-zinc-800 dark:bg-zinc-900",
            align === "end" ? "right-0" : "left-0",
          )}
        >
          {header && <div className="border-b border-zinc-100 px-2 pb-2 pt-1 dark:border-zinc-800">{header}</div>}
          {items.map((item) =>
            "href" in item ? (
              <Link key={item.label} href={item.href} role="menuitem" onClick={() => setOpen(false)} className={itemClass()}>
                {item.icon}
                {item.label}
              </Link>
            ) : (
              <button
                key={item.label}
                type="button"
                role="menuitem"
                aria-disabled={item.disabled}
                disabled={item.disabled}
                onClick={() => {
                  setOpen(false);
                  item.onSelect();
                }}
                className={cx(itemClass(item.danger), item.disabled && "cursor-not-allowed opacity-50")}
              >
                {item.icon}
                {item.label}
              </button>
            ),
          )}
        </div>
      )}
    </div>
  );
}

/** Modal dialog on the native <dialog> element: focus trap, Escape to close and backdrop come from the browser. */
export function Dialog({
  open,
  onClose,
  title,
  description,
  children,
  size = "md",
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: ReactNode;
  children: ReactNode;
  size?: "md" | "lg";
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(e) => e.target === ref.current && onClose()}
      aria-label={title}
      className={cx(
        "m-auto w-[calc(100%-2rem)] rounded-2xl border border-zinc-200 bg-white p-0 text-zinc-900 shadow-2xl backdrop:bg-navy-950/50 backdrop:backdrop-blur-sm dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-100",
        size === "lg" ? "max-w-3xl" : "max-w-lg",
      )}
    >
      {open && (
        <div>
          <header className="flex items-start justify-between gap-4 border-b border-zinc-200 px-5 py-4 dark:border-zinc-800">
            <div>
              <h2 className="text-base font-semibold">{title}</h2>
              {description && <p className="mt-0.5 text-sm text-zinc-500">{description}</p>}
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              className={cx("rounded-md p-1 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700 dark:hover:bg-zinc-800", focusRing)}
            >
              <X className="size-5" />
            </button>
          </header>
          <div className="max-h-[75vh] overflow-y-auto px-5 py-4">{children}</div>
        </div>
      )}
    </dialog>
  );
}

/** Labelled range slider showing its current value. */
export function Slider({
  label,
  value,
  onChange,
  min = 0,
  max = 100,
  step = 1,
  format = (v) => String(v),
  hint,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  step?: number;
  format?: (value: number) => string;
  hint?: string;
}) {
  const id = useId();
  return (
    <div>
      <div className="flex items-center justify-between text-xs">
        <label htmlFor={id} className="font-medium text-zinc-600 dark:text-zinc-300">
          {label}
        </label>
        <span className="rounded-md bg-brand-50 px-1.5 py-0.5 font-semibold tabular-nums text-brand-700 dark:bg-brand-950 dark:text-brand-300">
          {format(value)}
        </span>
      </div>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        aria-valuetext={format(value)}
        className="mt-2 w-full cursor-pointer"
      />
      {hint && <p className="mt-1 text-[11px] text-zinc-500">{hint}</p>}
    </div>
  );
}

export type SortState<K extends string> = { key: K; direction: "asc" | "desc" };

/** Clickable column header for sortable tables (aria-sort reflects the current order). */
export function SortHeader<K extends string>({
  label,
  sortKey,
  sort,
  onSort,
  className,
}: {
  label: string;
  sortKey: K;
  sort: SortState<K>;
  onSort: (sort: SortState<K>) => void;
  className?: string;
}) {
  const active = sort.key === sortKey;
  const Icon = !active ? ArrowUpDown : sort.direction === "asc" ? ArrowUp : ArrowDown;
  return (
    <th
      scope="col"
      aria-sort={active ? (sort.direction === "asc" ? "ascending" : "descending") : "none"}
      className={cx("px-4 py-2.5 font-medium", className)}
    >
      <button
        type="button"
        onClick={() => onSort({ key: sortKey, direction: active && sort.direction === "desc" ? "asc" : "desc" })}
        className={cx("inline-flex items-center gap-1 rounded hover:text-zinc-900 dark:hover:text-zinc-100", active && "text-zinc-900 dark:text-zinc-100", focusRing)}
      >
        {label}
        <Icon className={cx("size-3", !active && "opacity-40")} aria-hidden />
      </button>
    </th>
  );
}

export function Pagination({
  page,
  pageCount,
  total,
  pageSize,
  onPage,
}: {
  page: number;
  pageCount: number;
  total: number;
  pageSize: number;
  onPage: (page: number) => void;
}) {
  if (total === 0) return null;
  const from = (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);
  const button = "inline-flex size-8 items-center justify-center rounded-md border border-zinc-200 text-zinc-600 hover:bg-zinc-50 disabled:opacity-40 dark:border-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-800";
  return (
    <nav aria-label="Pagination" className="flex items-center justify-between gap-3 border-t border-zinc-200 px-4 py-3 text-xs text-zinc-500 dark:border-zinc-800">
      <span>
        {from}–{to} of {total}
      </span>
      <div className="flex items-center gap-1">
        <button type="button" className={cx(button, focusRing)} disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label="Previous page">
          <ChevronLeft className="size-4" />
        </button>
        <span className="px-2 tabular-nums">
          Page {page} / {pageCount}
        </span>
        <button type="button" className={cx(button, focusRing)} disabled={page >= pageCount} onClick={() => onPage(page + 1)} aria-label="Next page">
          <ChevronRight className="size-4" />
        </button>
      </div>
    </nav>
  );
}

export function usePaged<T>(items: T[], pageSize: number) {
  const [page, setPage] = useState(1);
  const pageCount = Math.max(1, Math.ceil(items.length / pageSize));
  const current = Math.min(page, pageCount);
  return {
    page: current,
    pageCount,
    setPage,
    rows: items.slice((current - 1) * pageSize, current * pageSize),
  };
}
