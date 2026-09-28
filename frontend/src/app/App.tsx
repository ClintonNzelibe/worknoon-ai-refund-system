import { CustomerRefundExperience } from "../features/refunds/CustomerRefundExperience";
import { SupportDashboard } from "../features/support/SupportDashboard";

export function App() {
  return window.location.pathname.startsWith("/support")
    ? <SupportDashboard />
    : <CustomerRefundExperience />;
}
