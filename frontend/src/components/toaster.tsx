"use client";

import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { CheckCircle2, X, XCircle } from "lucide-react";

import { cx } from "./ui";

type Toast = { id: number; tone: "success" | "error"; message: string };
type Notify = (message: string, tone?: Toast["tone"]) => void;

const ToastContext = createContext<Notify>(() => {});

/** Short-lived confirmations for actions ("Added to the pipeline"), announced to screen readers. */
export function Toaster({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const dismiss = useCallback((id: number) => setToasts((current) => current.filter((t) => t.id !== id)), []);
  const notify = useCallback<Notify>(
    (message, tone = "success") => {
      const id = Date.now() + Math.random();
      setToasts((current) => [...current.slice(-3), { id, tone, message }]);
      setTimeout(() => dismiss(id), tone === "error" ? 8000 : 4000);
    },
    [dismiss],
  );

  return (
    <ToastContext.Provider value={notify}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed inset-x-0 bottom-0 z-50 flex flex-col items-center gap-2 p-4 sm:items-end"
        style={{ paddingBottom: "max(1rem, env(safe-area-inset-bottom))" }}
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            role={toast.tone === "error" ? "alert" : "status"}
            className={cx(
              "pointer-events-auto flex w-full max-w-sm items-start gap-2 rounded-lg border bg-white px-3 py-2.5 text-sm shadow-lg dark:bg-zinc-900",
              toast.tone === "error" ? "border-red-200 dark:border-red-900" : "border-zinc-200 dark:border-zinc-800",
            )}
          >
            {toast.tone === "error" ? (
              <XCircle className="mt-0.5 size-4 shrink-0 text-red-600" aria-hidden />
            ) : (
              <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emerald-600" aria-hidden />
            )}
            <p className="flex-1">{toast.message}</p>
            <button
              type="button"
              onClick={() => dismiss(toast.id)}
              className="rounded text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200"
              aria-label="Dismiss"
            >
              <X className="size-4" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): Notify {
  return useContext(ToastContext);
}

/** Show an action's result as a toast: `{ok}` as success, `{error}` as error. */
export function useActionToast() {
  const notify = useToast();
  return (state: { ok?: string; error?: string } | null | undefined) => {
    if (state?.error) notify(state.error, "error");
    else if (state?.ok) notify(state.ok);
  };
}
