"use client";

import { useEffect, useRef, useState, type MouseEvent } from "react";

import {
  COOKIE_CONSENT_OPEN_EVENT,
  getCookieConsentPreferences,
  saveCookieConsentPreferences,
  type CookieConsentPreferences,
} from "@/lib/cookie-consent";

import styles from "./cookie-consent.module.css";

type BannerState = "hidden" | "visible" | "leaving";

const defaultPreferences = {
  analytics: false,
  marketing: false,
};

function selectionFromPreferences(preferences: CookieConsentPreferences | null) {
  return preferences
    ? { analytics: preferences.analytics, marketing: preferences.marketing }
    : defaultPreferences;
}

export function CookieConsent() {
  const [isReady, setIsReady] = useState(false);
  const [bannerState, setBannerState] = useState<BannerState>("hidden");
  const [isPreferencesOpen, setIsPreferencesOpen] = useState(false);
  const [selection, setSelection] = useState(defaultPreferences);
  const dialogRef = useRef<HTMLDivElement>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const initialFrame = window.requestAnimationFrame(() => {
      const savedPreferences = getCookieConsentPreferences();
      setSelection(selectionFromPreferences(savedPreferences));
      setBannerState(savedPreferences ? "hidden" : "visible");
      setIsReady(true);
    });

    const handleOpenPreferences = () => {
      returnFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      const currentPreferences = getCookieConsentPreferences();
      setSelection(selectionFromPreferences(currentPreferences));
      setIsPreferencesOpen(true);
    };

    window.addEventListener(COOKIE_CONSENT_OPEN_EVENT, handleOpenPreferences);
    return () => {
      window.cancelAnimationFrame(initialFrame);
      window.removeEventListener(COOKIE_CONSENT_OPEN_EVENT, handleOpenPreferences);
    };
  }, []);

  useEffect(() => {
    if (!isPreferencesOpen) {
      return;
    }

    const dialog = dialogRef.current;
    dialog?.focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        closePreferences();
        return;
      }

      if (event.key !== "Tab" || !dialog) {
        return;
      }

      const focusableElements = dialog.querySelectorAll<HTMLElement>(
        'button:not([disabled]), input:not([disabled]), a[href]',
      );
      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];

      if (!firstElement || !lastElement) {
        return;
      }

      if (event.shiftKey && document.activeElement === firstElement) {
        event.preventDefault();
        lastElement.focus();
      } else if (!event.shiftKey && document.activeElement === lastElement) {
        event.preventDefault();
        firstElement.focus();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isPreferencesOpen]);

  function closePreferences() {
    setIsPreferencesOpen(false);
    window.setTimeout(() => returnFocusRef.current?.focus(), 0);
  }

  function dismissBanner() {
    setBannerState("leaving");
    window.setTimeout(() => setBannerState("hidden"), 280);
  }

  function saveSelection(nextSelection: typeof selection) {
    saveCookieConsentPreferences(nextSelection);
    setSelection(nextSelection);
    closePreferences();
    dismissBanner();
  }

  function acceptAll() {
    saveSelection({ analytics: true, marketing: true });
  }

  function rejectOptionalCookies() {
    saveSelection(defaultPreferences);
  }

  function openPreferencesFromBanner(event: MouseEvent<HTMLButtonElement>) {
    returnFocusRef.current = event.currentTarget;
    setIsPreferencesOpen(true);
  }

  if (!isReady) {
    return null;
  }

  return (
    <>
      {bannerState !== "hidden" && (
        <section
          aria-label="Preferencias de cookies"
          className={`${styles.banner} ${bannerState === "leaving" ? styles.bannerLeaving : ""}`}
        >
          <div className={styles.bannerContent}>
            <div className={styles.bannerCopy}>
              <p className={styles.eyebrow}>Cookies</p>
              <p>
                Usamos cookies necesarias para que la web funcione correctamente. Puedes aceptar cookies de analítica, rechazar las opcionales o configurar tus preferencias.
              </p>
              <a href="/politica-de-cookies">Política de cookies</a>
            </div>
            <div className={styles.bannerActions}>
              <button className={styles.primaryAction} onClick={acceptAll} type="button">
                Aceptar todas
              </button>
              <button className={styles.secondaryAction} onClick={rejectOptionalCookies} type="button">
                Rechazar
              </button>
              <button className={styles.textAction} onClick={openPreferencesFromBanner} type="button">
                Configurar
              </button>
            </div>
          </div>
        </section>
      )}

      {isPreferencesOpen && (
        <div className={styles.backdrop}>
          <div
            aria-labelledby="cookie-preferences-title"
            aria-modal="true"
            className={styles.dialog}
            ref={dialogRef}
            role="dialog"
            tabIndex={-1}
          >
            <div className={styles.dialogHeader}>
              <div>
                <p className={styles.eyebrow}>Preferencias de cookies</p>
                <h2 id="cookie-preferences-title">Elige cómo quieres que usemos las cookies.</h2>
              </div>
              <button aria-label="Cerrar preferencias de cookies" className={styles.closeButton} onClick={closePreferences} type="button">
                <span aria-hidden="true">×</span>
              </button>
            </div>

            <div className={styles.preferenceList}>
              <label className={styles.preference}>
                <span>
                  <strong>Necesarias</strong>
                  <small>Permiten que las funciones esenciales, como la sesión, funcionen correctamente.</small>
                </span>
                <input aria-label="Cookies necesarias" checked disabled type="checkbox" />
              </label>
              <label className={styles.preference}>
                <span>
                  <strong>Analítica</strong>
                  <small>Google Analytics se activa únicamente cuando aceptas esta categoría.</small>
                </span>
                <input
                  aria-label="Cookies analíticas"
                  checked={selection.analytics}
                  onChange={(event) => setSelection((current) => ({ ...current, analytics: event.target.checked }))}
                  type="checkbox"
                />
              </label>
              <label className={styles.preference}>
                <span>
                  <strong>Marketing</strong>
                  <small>Preparada para futuras tecnologías de marketing. Actualmente no se utiliza.</small>
                </span>
                <input
                  aria-label="Cookies de marketing"
                  checked={selection.marketing}
                  onChange={(event) => setSelection((current) => ({ ...current, marketing: event.target.checked }))}
                  type="checkbox"
                />
              </label>
            </div>

            <div className={styles.dialogActions}>
              <button className={styles.secondaryAction} onClick={closePreferences} type="button">
                Cancelar
              </button>
              <button className={styles.primaryAction} onClick={() => saveSelection(selection)} type="button">
                Guardar preferencias
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
