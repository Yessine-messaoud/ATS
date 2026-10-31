"use client";

import { useTransition } from "react";
import { Ban, Check, RotateCcw } from "lucide-react";

import { useActionToast } from "@/components/toaster";
import { Button } from "@/components/ui";
import type { Organization } from "@/lib/api";

import { setCompanyStatus } from "../actions";

/** Approve a pending company, suspend an active one, or reinstate a suspended one. */
export function CompanyActions({ organization }: { organization: Pick<Organization, "id" | "status"> }) {
  const [pending, startTransition] = useTransition();
  const toast = useActionToast();
  const set = (status: "active" | "suspended") => startTransition(async () => toast(await setCompanyStatus(organization.id, status)));

  if (organization.status === "pending") {
    return (
      <div className="flex gap-2">
        <Button size="sm" variant="ghost" disabled={pending} icon={<Ban className="size-3.5" />} onClick={() => set("suspended")}>
          Reject
        </Button>
        <Button size="sm" loading={pending} icon={<Check className="size-3.5" />} onClick={() => set("active")}>
          Approve
        </Button>
      </div>
    );
  }
  return organization.status === "active" ? (
    <Button size="sm" variant="ghost" disabled={pending} icon={<Ban className="size-3.5" />} onClick={() => set("suspended")}>
      Suspend
    </Button>
  ) : (
    <Button size="sm" variant="secondary" disabled={pending} icon={<RotateCcw className="size-3.5" />} onClick={() => set("active")}>
      Reinstate
    </Button>
  );
}
