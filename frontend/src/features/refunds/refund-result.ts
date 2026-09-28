import type { RefundRequestResult } from "./types";

export interface RefundDecisionCounts {
  approved: number;
  rejected: number;
  escalated: number;
  pending: number;
}

export function refundDecisionCounts(result: RefundRequestResult): RefundDecisionCounts {
  return result.items.reduce<RefundDecisionCounts>((counts, item) => {
    counts[item.decision] += 1;
    return counts;
  }, { approved: 0, rejected: 0, escalated: 0, pending: 0 });
}

// The request status and the item decisions are both server-authoritative. Keep
// refreshing until every item that required human review has a final decision.
export function shouldPollRefundResult(result: RefundRequestResult): boolean {
  return result.status === "escalated"
    || result.items.some((item) => item.decision === "escalated");
}

export function refundOutcomeTitle(outcome: RefundRequestResult["status"]): string {
  if (outcome === "approved") return "Your request is approved";
  if (outcome === "escalated") return "Your request needs a quick review";
  if (outcome === "rejected") return "Your request is not eligible";
  return "Your request is being reviewed";
}
