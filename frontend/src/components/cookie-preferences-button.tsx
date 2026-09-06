"use client";

import { openCookiePreferences } from "@/lib/cookie-consent";

type CookiePreferencesButtonProps = {
  className?: string;
};

export function CookiePreferencesButton({ className }: CookiePreferencesButtonProps) {
  return (
    <button className={className} onClick={openCookiePreferences} type="button">
      Configurar cookies
    </button>
  );
}
