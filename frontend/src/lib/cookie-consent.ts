export const COOKIE_CONSENT_STORAGE_KEY = "aurea_cookie_consent_v1";
export const COOKIE_CONSENT_OPEN_EVENT = "aurea:open-cookie-preferences";
export const COOKIE_CONSENT_UPDATED_EVENT = "aurea:cookie-consent-updated";

export type CookieConsentPreferences = {
  necessary: true;
  analytics: boolean;
  marketing: boolean;
  updatedAt: string;
};

type CookieConsentSelection = Pick<CookieConsentPreferences, "analytics" | "marketing">;

export function createCookieConsentPreferences(
  selection: CookieConsentSelection,
): CookieConsentPreferences {
  return {
    necessary: true,
    analytics: selection.analytics,
    marketing: selection.marketing,
    updatedAt: new Date().toISOString(),
  };
}

export function getCookieConsentPreferences(): CookieConsentPreferences | null {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    const storedValue = window.localStorage.getItem(COOKIE_CONSENT_STORAGE_KEY);
    if (!storedValue) {
      return null;
    }

    const parsedValue: unknown = JSON.parse(storedValue);
    if (
      !parsedValue ||
      typeof parsedValue !== "object" ||
      !(
        "necessary" in parsedValue &&
        "analytics" in parsedValue &&
        "marketing" in parsedValue &&
        "updatedAt" in parsedValue
      ) ||
      parsedValue.necessary !== true ||
      typeof parsedValue.analytics !== "boolean" ||
      typeof parsedValue.marketing !== "boolean" ||
      typeof parsedValue.updatedAt !== "string"
    ) {
      return null;
    }

    return parsedValue as CookieConsentPreferences;
  } catch {
    return null;
  }
}

export function saveCookieConsentPreferences(
  selection: CookieConsentSelection,
): CookieConsentPreferences {
  const preferences = createCookieConsentPreferences(selection);
  window.localStorage.setItem(COOKIE_CONSENT_STORAGE_KEY, JSON.stringify(preferences));
  window.dispatchEvent(
    new CustomEvent<CookieConsentPreferences>(COOKIE_CONSENT_UPDATED_EVENT, {
      detail: preferences,
    }),
  );
  return preferences;
}

export function hasAnalyticsConsent(): boolean {
  return getCookieConsentPreferences()?.analytics === true;
}

export function hasMarketingConsent(): boolean {
  return getCookieConsentPreferences()?.marketing === true;
}

export function openCookiePreferences(): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(COOKIE_CONSENT_OPEN_EVENT));
  }
}
