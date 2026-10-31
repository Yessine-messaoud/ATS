import Link from "next/link";
import type { ReactNode } from "react";
import { ExternalLink, FileText, Github, Globe, Linkedin, Mail, MapPin, Phone } from "lucide-react";

import type { Candidate, CandidateDocument } from "@/lib/api";

import { Empty } from "./ui";

/** Contact details from the CV (shown to recruiters; hidden from scoring, the assistant and blind views). */
export function ContactList({ candidate }: { candidate: Candidate }) {
  const identity = candidate.profile.identity ?? {};
  const location = [identity.location?.city, identity.location?.country].filter(Boolean).join(", ");
  const links = [
    identity.email && { icon: <Mail />, label: identity.email, href: `mailto:${identity.email}` },
    identity.phone && { icon: <Phone />, label: identity.phone },
    location && { icon: <MapPin />, label: location },
    identity.linkedin_url && { icon: <Linkedin />, label: "LinkedIn", href: identity.linkedin_url },
    identity.github_url && { icon: <Github />, label: "GitHub", href: identity.github_url },
    identity.portfolio_url && { icon: <Globe />, label: "Portfolio", href: identity.portfolio_url },
  ].filter(Boolean) as { icon: ReactNode; label: string; href?: string }[];
  if (links.length === 0) return <p className="text-sm text-zinc-500">No contact details in the CV.</p>;
  return (
    <ul className="space-y-2 text-sm">
      {links.map((link) => (
        <li key={link.label} className="flex items-center gap-2 text-zinc-600 dark:text-zinc-300">
          <span className="text-zinc-400 [&>svg]:size-4">{link.icon}</span>
          {link.href ? (
            <a href={link.href} target={link.href.startsWith("http") ? "_blank" : undefined} rel="noreferrer" className="truncate hover:text-brand-600 hover:underline">
              {link.label}
            </a>
          ) : (
            <span className="truncate">{link.label}</span>
          )}
        </li>
      ))}
    </ul>
  );
}

/** The uploaded CV: inline PDF preview when possible, otherwise the extracted text. */
export function DocumentPreview({ candidateId, document, height = "42rem" }: { candidateId: string; document: CandidateDocument | null; height?: string }) {
  if (!document) return <Empty icon={<FileText />}>No source document stored.</Empty>;
  if (document.purged_at) {
    return (
      <Empty icon={<FileText />} title="Document deleted">
        Deleted on {new Date(document.purged_at).toLocaleDateString("en-GB")} under the retention policy. The extracted profile is kept.
      </Empty>
    );
  }
  const isPdf = document.mime_type === "application/pdf";
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2 text-xs text-zinc-500">
        <span className="truncate">{document.filename ?? "Uploaded document"}</span>
        <Link href={`/candidates/${candidateId}/file`} target="_blank" className="flex shrink-0 items-center gap-1 font-medium text-brand-600 hover:underline dark:text-brand-400">
          Open in a new tab <ExternalLink className="size-3" aria-hidden />
        </Link>
      </div>
      {isPdf ? (
        <object
          data={`/candidates/${candidateId}/file`}
          type="application/pdf"
          aria-label="CV preview"
          className="w-full rounded-lg border border-zinc-200 bg-zinc-100 dark:border-zinc-800 dark:bg-zinc-950"
          style={{ height }}
        >
          <ExtractedText text={document.raw_text} height={height} />
        </object>
      ) : (
        <ExtractedText text={document.raw_text} height={height} />
      )}
    </div>
  );
}

export function ExtractedText({ text, height = "32rem" }: { text: string | null | undefined; height?: string }) {
  return (
    <pre
      className="overflow-auto whitespace-pre-wrap rounded-lg border border-zinc-200 bg-zinc-50 p-4 font-mono text-xs leading-relaxed dark:border-zinc-800 dark:bg-zinc-950"
      style={{ maxHeight: height }}
    >
      {text ?? "No text extracted."}
    </pre>
  );
}
