export type RefundReasonCode = "damaged" | "incorrect" | "other";

export interface OrderSummary {
  reference: string;
  status: string;
  currency: string;
  total_amount: string;
  ordered_at: string;
}

export interface CustomerOrderLookup {
  orders: OrderSummary[];
}

export interface OrderItem {
  id: number;
  sku: string;
  product_name: string;
  unit_price: string;
  quantity: number;
  is_final_sale: boolean;
}

export interface Order {
  reference: string;
  status: string;
  currency: string;
  total_amount: string;
  ordered_at: string;
  items: OrderItem[];
}

export interface RefundRequestItem {
  id: number;
  order_item: OrderItem;
  requested_quantity: number;
  requested_amount: string;
  decision: "approved" | "rejected" | "escalated" | "pending";
  decision_reason: string;
}

export interface CustomerAIRefundAssistance {
  available: boolean;
  customer_message?: string;
}

export interface AIRefundAssistance extends CustomerAIRefundAssistance {
  error_code?: string;
  message?: string;
  classification?: "consistent" | "conflicting" | "unclear";
  risk?: "low" | "medium" | "high";
  summary?: string;
  reasoning?: string;
  policy_alignment?: "aligned" | "concern";
}

export interface RefundRequestResult {
  id: number;
  order_reference: string;
  customer_id: number;
  status: "approved" | "rejected" | "escalated" | "pending";
  policy_outcome: "approved" | "rejected" | "escalated" | null;
  reason_code: RefundReasonCode;
  reason: string;
  requested_amount: string;
  resolution_note: string;
  resolved_at: string | null;
  created_at: string;
  items: RefundRequestItem[];
  ai_assistance?: CustomerAIRefundAssistance;
}

export interface CreateRefundRequestInput {
  order_reference: string;
  reason_code: RefundReasonCode;
  reason: string;
  items: Array<{
    order_item_id: number;
    requested_quantity: number;
  }>;
}

export interface AuditLog {
  id: number;
  action: string;
  message: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface SupportRefundRequest {
  id: number;
  customer_name: string;
  customer_email: string;
  order_reference: string;
  currency: string;
  requested_amount: string;
  status: "approved" | "rejected" | "escalated" | "pending" | "paid" | "cancelled";
  reason_code: RefundReasonCode;
  reason: string;
  resolution_note: string;
  created_at: string;
  resolved_at: string | null;
  items: RefundRequestItem[];
  audit_logs: AuditLog[];
  ai_assistance?: AIRefundAssistance;
}

export interface SupportRefundPage {
  count: number;
  page: number;
  page_size: number;
  total_pages: number;
  results: SupportRefundRequest[];
}
