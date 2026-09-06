"use client";

import { useEffect, useState } from "react";

import styles from "./scroll-to-top.module.css";

const VISIBILITY_THRESHOLD = 500;

export function ScrollToTop() {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const updateVisibility = () => {
      setIsVisible(window.scrollY >= VISIBILITY_THRESHOLD);
    };

    updateVisibility();
    window.addEventListener("scroll", updateVisibility, { passive: true });

    return () => {
      window.removeEventListener("scroll", updateVisibility);
    };
  }, []);

  const scrollToTop = () => {
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    window.scrollTo({ top: 0, behavior: reducedMotion ? "auto" : "smooth" });
  };

  return (
    <button
      aria-label="Volver arriba"
      className={`${styles.button} ${isVisible ? styles.visible : ""}`}
      onClick={scrollToTop}
      type="button"
    >
      <svg aria-hidden="true" fill="none" focusable="false" viewBox="0 0 24 24">
        <path d="m6 14 6-6 6 6" />
        <path d="M12 9v9" />
      </svg>
    </button>
  );
}
