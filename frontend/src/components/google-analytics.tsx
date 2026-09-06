"use client";

import Script from "next/script";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import {
  COOKIE_CONSENT_UPDATED_EVENT,
  getCookieConsentPreferences,
  type CookieConsentPreferences,
} from "@/lib/cookie-consent";

const measurementId = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID;

type ConsentState = "denied" | "granted";

declare global {
  interface Window {
    dataLayer?: unknown[][];
    gtag?: (...args: unknown[]) => void;
  }
}

function ensureGtag() {
  window.dataLayer ??= [];
  window.gtag ??= (...args: unknown[]) => window.dataLayer?.push(args);
  return window.gtag;
}

function updateGoogleConsent(analytics: boolean) {
  const gtag = ensureGtag();
  const analyticsStorage: ConsentState = analytics ? "granted" : "denied";

  gtag("consent", "update", {
    analytics_storage: analyticsStorage,
    ad_storage: "denied",
    ad_user_data: "denied",
    ad_personalization: "denied",
  });
}

export function GoogleAnalytics() {
  const pathname = usePathname();
  const [analyticsGranted, setAnalyticsGranted] = useState(false);
  const [shouldLoadScript, setShouldLoadScript] = useState(false);
  const [isScriptReady, setIsScriptReady] = useState(false);

  useEffect(() => {
    if (!measurementId) {
      return;
    }

    const gtag = ensureGtag();
    gtag("consent", "default", {
      analytics_storage: "denied",
      ad_storage: "denied",
      ad_user_data: "denied",
      ad_personalization: "denied",
    });

    const applyPreferences = (preferences: CookieConsentPreferences | null) => {
      const analytics = preferences?.analytics === true;
      updateGoogleConsent(analytics);
      setAnalyticsGranted(analytics);
      setShouldLoadScript((current) => current || analytics);
    };

    const initialFrame = window.requestAnimationFrame(() => {
      applyPreferences(getCookieConsentPreferences());
    });

    const handleConsentUpdate = (event: Event) => {
      applyPreferences((event as CustomEvent<CookieConsentPreferences>).detail);
    };

    window.addEventListener(COOKIE_CONSENT_UPDATED_EVENT, handleConsentUpdate);
    return () => {
      window.cancelAnimationFrame(initialFrame);
      window.removeEventListener(COOKIE_CONSENT_UPDATED_EVENT, handleConsentUpdate);
    };
  }, []);

  useEffect(() => {
    if (!measurementId || !analyticsGranted || !isScriptReady) {
      return;
    }

    window.gtag?.("event", "page_view", {
      page_path: pathname,
    });
  }, [analyticsGranted, isScriptReady, pathname]);

  if (!measurementId || !shouldLoadScript) {
    return null;
  }

  return (
    <Script
      id="aurea-google-analytics"
      onLoad={() => {
        window.gtag?.("js", new Date());
        window.gtag?.("config", measurementId, { send_page_view: false });
        setIsScriptReady(true);
      }}
      src={`https://www.googletagmanager.com/gtag/js?id=${measurementId}`}
      strategy="afterInteractive"
    />
  );
}
