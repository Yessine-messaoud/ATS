// Option lists for forms, checked against the backend's enums by the generated types.
import type { components } from "./api-types";

type S = components["schemas"];

export const SENIORITY = [
  "intern",
  "junior",
  "mid",
  "senior",
  "lead",
  "manager",
  "director",
  "executive",
] as const satisfies readonly S["SeniorityLevel"][];

export const WORK_MODES = ["on_site", "hybrid", "remote"] as const satisfies readonly S["WorkMode"][];

export const CONTRACT_TYPES = [
  "permanent",
  "fixed_term",
  "temporary",
  "internship",
  "apprenticeship",
  "freelance",
] as const satisfies readonly S["ContractType"][];

export const LANGUAGE_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2", "native"] as const satisfies readonly S["LanguageLevel"][];

export const REQUIREMENT_KINDS = ["required", "preferred"] as const satisfies readonly S["RequirementKind"][];

export const STAGES = [
  "new",
  "screening",
  "interview",
  "offer",
  "hired",
  "rejected",
  "withdrawn",
] as const satisfies readonly S["ApplicationStage"][];

export const STAGE_LABELS: Record<(typeof STAGES)[number], string> = {
  new: "New",
  screening: "Screening",
  interview: "Interview",
  offer: "Offer",
  hired: "Hired",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
};

export const FLAG_LABELS: Record<string, string> = {
  hidden_text: "Hidden text in document",
  possible_prompt_injection: "Possible prompt injection",
  ocr_used: "Scanned document (OCR)",
  ocr_unavailable: "Scanned document, OCR unavailable",
  low_text: "Very little text",
  pages_truncated: "Only the first pages were read",
  no_cv_attachment: "Email without CV attachment",
};
