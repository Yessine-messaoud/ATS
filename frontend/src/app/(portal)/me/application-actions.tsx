"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, useTransition } from "react";

import { Dialog } from "@/components/interactive";
import { useActionToast } from "@/components/toaster";
import { Button } from "@/components/ui";

import { withdrawApplication } from "../actions";

/** Refreshes the page every few seconds while a CV is being read. */
export function AutoRefresh({ seconds = 5 }: { seconds?: number }) {
  const router = useRouter();
  useEffect(() => {
    const timer = setInterval(() => router.refresh(), seconds * 1000);
    return () => clearInterval(timer);
  }, [router, seconds]);
  return null;
}

export function WithdrawButton({ id, title }: { id: string; title: string }) {
  const [open, setOpen] = useState(false);
  const [pending, startTransition] = useTransition();
  const toast = useActionToast();
  return (
    <>
      <Button size="sm" variant="ghost" onClick={() => setOpen(true)}>
        Withdraw
      </Button>
      <Dialog open={open} onClose={() => setOpen(false)} title="Withdraw your application?" description={title}>
        <p className="text-sm text-zinc-600 dark:text-zinc-300">The company is told that you withdrew. You cannot apply to this job again afterwards.</p>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setOpen(false)}>
            Keep it
          </Button>
          <Button
            variant="danger"
            loading={pending}
            onClick={() =>
              startTransition(async () => {
                toast(await withdrawApplication(id));
                setOpen(false);
              })
            }
          >
            Withdraw
          </Button>
        </div>
      </Dialog>
    </>
  );
}
