/**
 * Public checkout-provider feature flags.
 *
 * Next.js inlines NEXT_PUBLIC_* values at build time, so production must be
 * rebuilt after changing this flag.
 */
export function isPayPalPaymentsEnabled(value: string | undefined): boolean {
  return value === "true";
}

export const paypalPaymentsEnabled = isPayPalPaymentsEnabled(
  process.env.NEXT_PUBLIC_PAYPAL_ENABLED,
);
