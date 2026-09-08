import { describe, expect, it } from "vitest";

import {
  getPaymentReturnOutcome,
  getPaymentReturnReference,
  reservePaymentSuccessAlert,
} from "./payment-return-state";

const reservation = {
  id: 42,
  tool: { id: 7, name: "Mini excavadora" },
  start_date: "2026-09-10",
  end_date: "2026-09-12",
  status: "pending_payment" as const,
  fulfillment_method: "pickup" as const,
  delivery_address: null,
  total_amount: "120.00",
  deposit_amount: "150.00",
};

function paymentStatus(overrides: Partial<{
  payment_status: "pending" | "paid" | "failed" | "expired" | "requires_review";
  reservation_status: typeof reservation.status | "confirmed";
  payment_expired: boolean;
}> = {}) {
  return {
    payment_status: "pending" as const,
    reservation_status: "pending_payment" as const,
    payment_expired: false,
    reservation,
    ...overrides,
  };
}

describe("payment return references", () => {
  it("uses the Stripe session only to query the real backend state", () => {
    expect(getPaymentReturnReference(new URLSearchParams("provider=stripe&session_id=cs_test_123"))).toEqual({
      provider: "stripe",
      externalPaymentId: "cs_test_123",
    });
  });

  it("uses the PayPal return token and rejects URLs without a supported provider", () => {
    expect(getPaymentReturnReference(new URLSearchParams("provider=paypal&token=ORDER-123"))).toEqual({
      provider: "paypal",
      externalPaymentId: "ORDER-123",
    });
    expect(getPaymentReturnReference(new URLSearchParams("payment=success"))).toEqual({
      provider: null,
      externalPaymentId: null,
    });
  });
});

describe("payment return state", () => {
  it("only treats a paid and confirmed backend response as success", () => {
    expect(getPaymentReturnOutcome(paymentStatus({
      payment_status: "paid",
      reservation_status: "confirmed",
    }))).toBe("confirmed");
    expect(getPaymentReturnOutcome(paymentStatus({ payment_status: "paid" }))).toBe("waiting");
  });

  it("keeps pending webhooks waiting and handles review, expiry and missing success neutrally", () => {
    expect(getPaymentReturnOutcome(paymentStatus())).toBe("waiting");
    expect(getPaymentReturnOutcome(paymentStatus({ payment_status: "requires_review" }))).toBe("requires_review");
    expect(getPaymentReturnOutcome(paymentStatus({ payment_expired: true }))).toBe("expired");
  });

  it("reserves the SweetAlert display once for the same payment return", () => {
    const values = new Map<string, string>();
    const storage = {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
    };

    expect(reservePaymentSuccessAlert(storage, "payment:stripe:cs_test_123")).toBe(true);
    expect(reservePaymentSuccessAlert(storage, "payment:stripe:cs_test_123")).toBe(false);
  });
});
