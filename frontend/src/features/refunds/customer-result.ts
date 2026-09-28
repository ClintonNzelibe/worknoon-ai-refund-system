import type { RefundRequestResult } from "./types";

export type CustomerRefundStatus = "approved" | "denied" | "review" | "pending";

export interface CustomerRefundPresentation {
  status: CustomerRefundStatus;
  title: string;
  statusLabel: string;
  explanation: string;
  nextSteps: string[];
  approvedAmount: string | null;
}

// This mapping deliberately uses only customer-safe data. Internal policy notes,
// decision reasons, AI risk, classification, and reasoning remain support-only.
export function customerRefundPresentation(result: RefundRequestResult): CustomerRefundPresentation {
  const hasReview = result.status === "escalated"
    || result.items.some((item) => item.decision === "escalated");
  const hasPending = result.status === "pending"
    || result.items.some((item) => item.decision === "pending");
  const approvedItems = result.items.filter((item) => item.decision === "approved");
  const hasApproval = result.status === "approved" || approvedItems.length > 0;
  const guidance = result.ai_assistance?.available
    ? result.ai_assistance.customer_message?.trim()
    : undefined;

  if (hasReview) {
    return {
      status: "review",
      title: "Needs a quick review",
      statusLabel: "Waiting for support review",
      explanation: guidance || "We received your request and our support team will review the details before a final decision is made.",
      nextSteps: [
        "We’ll update this request when the review is complete.",
        "Please provide clear photos of the damaged area and original packaging, along with a photo of the SKU or label and a brief timeline of when you opened the package. Please keep the item and packaging available in case our support team needs to inspect them.",
        "Your request is safely recorded, so you don’t need to submit it again.",
      ],
      approvedAmount: null,
    };
  }

  if (hasPending) {
    return {
      status: "pending",
      title: "We’re reviewing your request",
      statusLabel: "Review in progress",
      explanation: guidance || "We received your request and are checking the details.",
      nextSteps: ["We’ll update this request as soon as there is an outcome."],
      approvedAmount: null,
    };
  }

  if (hasApproval) {
    return {
      status: "approved",
      title: "Refund approved",
      statusLabel: "Approved",
      explanation: guidance || "Your refund request has been approved.",
      nextSteps: ["Your refund will be processed according to the store’s refund process."],
      approvedAmount: approvedItems.reduce((total, item) => total + Number(item.requested_amount), 0).toFixed(2),
    };
  }

  return {
    status: "denied",
    title: "Refund request not approved",
    statusLabel: "Not approved",
    explanation: guidance || "This refund request could not be approved at this time.",
    nextSteps: ["If you believe this decision is incorrect, please contact support with any additional information that may help us review your request."],
    approvedAmount: null,
  };
}

export function customerItemStatus(decision: RefundRequestResult["items"][number]["decision"]): string {
  if (decision === "approved") return "Approved";
  if (decision === "rejected") return "Not approved";
  if (decision === "escalated") return "Needs review";
  return "Reviewing";
}
