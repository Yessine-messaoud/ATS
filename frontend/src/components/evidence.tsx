import { Badge } from "./ui";

/** Shows whether an extracted item's evidence quote was found in the source document. */
export function EvidenceBadge({ verified, evidence }: { verified?: boolean | null; evidence?: string | null }) {
  if (verified === true) {
    return (
      <Badge tone="green" title={evidence ? `“${evidence}”` : "found in the document"}>
        verified
      </Badge>
    );
  }
  if (verified === false) {
    return (
      <Badge tone="red" title={evidence ? `Not found in the document: “${evidence}”` : "no supporting text found"}>
        unverified
      </Badge>
    );
  }
  return <Badge title="not checked against a document">unchecked</Badge>;
}

export function Quote({ text }: { text?: string | null }) {
  if (!text) return null;
  return <p className="mt-0.5 border-l-2 border-zinc-300 pl-2 text-xs italic text-zinc-500 dark:border-zinc-700">“{text}”</p>;
}
