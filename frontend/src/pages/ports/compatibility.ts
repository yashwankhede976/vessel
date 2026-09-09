/**
 * Client-side, deterministic vessel–berth compatibility check.
 *
 * This mirrors the backend rule engine's dimension logic (LOA/beam/draft/cargo)
 * for interactive UI feedback. It is NOT a substitute for the authoritative
 * backend engine — it works from the same published berth limits and applies
 * the same simple rules. No live data, no ML.
 */
import type { Berth } from "../../api";

export type CompatStatus = "COMPATIBLE" | "CONDITIONAL" | "INCOMPATIBLE" | "UNKNOWN";

export interface VesselSpec {
  loa: number;
  beam: number;
  draft: number;
  cargo?: string;
}

export interface BerthCompatResult {
  berthId: number;
  status: CompatStatus;
  reasons: string[];
}

const EPSILON = 0.001;

function num(value: string | null | undefined): number | null {
  if (value === null || value === undefined || value === "") return null;
  const n = Number(value);
  return Number.isNaN(n) ? null : n;
}

/** Evaluate one vessel against one berth using published limits. */
export function evaluateBerth(vessel: VesselSpec, berth: Berth): BerthCompatResult {
  const reasons: string[] = [];
  let fail = false;
  let unknown = false;

  const maxLoa = num(berth.max_loa);
  const maxBeam = num(berth.max_beam);
  const maxDraft = num(berth.max_draft);

  const dim = (label: string, value: number, limit: number | null, unit: string) => {
    if (limit === null) {
      unknown = true;
      reasons.push(`${label} limit not documented for this berth.`);
      return;
    }
    if (value > limit + EPSILON) {
      fail = true;
      reasons.push(`${label} ${value}${unit} exceeds berth limit ${limit}${unit}.`);
    }
  };

  dim("LOA", vessel.loa, maxLoa, "m");
  dim("Beam", vessel.beam, maxBeam, "m");
  dim("Draft", vessel.draft, maxDraft, "m");

  // Cargo compatibility (case-insensitive).
  if (vessel.cargo) {
    const supported = berth.supported_commodities.map((c) => c.toLowerCase());
    if (supported.length === 0) {
      unknown = true;
      reasons.push("Berth supported commodities not documented.");
    } else if (!supported.includes(vessel.cargo.toLowerCase())) {
      fail = true;
      reasons.push(`Cargo '${vessel.cargo}' not supported at this berth.`);
    }
  }

  let status: CompatStatus;
  if (fail) status = "INCOMPATIBLE";
  else if (unknown) status = "UNKNOWN";
  else status = "COMPATIBLE";

  return { berthId: berth.id, status, reasons };
}
