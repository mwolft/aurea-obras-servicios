import type { StripeCheckoutStatus } from "@/lib/api";

export type PaymentProvider = "stripe" | "paypal";

export type PaymentReturnOutcome = "confirmed" | "requires_review" | "expired" | "waiting";

export function getPaymentReturnReference(searchParams: URLSearchParams): {
  provider: PaymentProvider | null;
  externalPaymentId: string | null;
} {
  const provider = searchParams.get("provider");
  if (provider === "stripe") {
    return { provider, externalPaymentId: searchParams.get("session_id") };
  }

  if (provider === "paypal") {
    // PayPal appends its Order ID as `token` to the configured return URL.
    return {
      provider,
      externalPaymentId: searchParams.get("order_id") ?? searchParams.get("token"),
    };
  }

  return { provider: null, externalPaymentId: null };
}

export function getPaymentReturnOutcome(payment: StripeCheckoutStatus): PaymentReturnOutcome {
  if (payment.reservation_status === "confirmed" && payment.payment_status === "paid") {
    return "confirmed";
  }

  if (payment.payment_status === "requires_review") {
    return "requires_review";
  }

  if (payment.payment_expired || payment.payment_status === "expired") {
    return "expired";
  }

  return "waiting";
}

export function reservePaymentSuccessAlert(
  storage: Pick<Storage, "getItem" | "setItem">,
  key: string,
): boolean {
  if (storage.getItem(key)) {
    return false;
  }

  storage.setItem(key, "shown");
  return true;
}
