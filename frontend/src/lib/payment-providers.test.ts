import { describe, expect, it } from "vitest";

import { isPayPalPaymentsEnabled } from "./payment-providers";

describe("PayPal public checkout feature flag", () => {
  it("is disabled unless explicitly enabled", () => {
    expect(isPayPalPaymentsEnabled(undefined)).toBe(false);
    expect(isPayPalPaymentsEnabled("false")).toBe(false);
    expect(isPayPalPaymentsEnabled("TRUE")).toBe(false);
    expect(isPayPalPaymentsEnabled("true")).toBe(true);
  });
});
