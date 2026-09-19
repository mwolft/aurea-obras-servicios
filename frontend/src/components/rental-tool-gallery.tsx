"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { PointerEvent } from "react";

import type { CatalogImage } from "@/lib/api";

import styles from "./rental-tool-gallery.module.css";

type RentalToolGalleryProps = {
  imageAlt: string;
  images: CatalogImage[];
  toolName: string;
};

type SwipeStart = {
  pointerId: number;
  x: number;
  y: number;
};

const SWIPE_THRESHOLD_PX = 48;

function ChevronIcon({ direction }: { direction: "previous" | "next" }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d={direction === "previous" ? "m14.5 5-7 7 7 7" : "m9.5 5 7 7-7 7"} />
    </svg>
  );
}

export function RentalToolGallery({ imageAlt, images, toolName }: RentalToolGalleryProps) {
  const [selectedImageIndex, setSelectedImageIndex] = useState(0);
  const [isLightboxOpen, setIsLightboxOpen] = useState(false);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const mainImageButtonRef = useRef<HTMLButtonElement>(null);
  const swipeStartRef = useRef<SwipeStart | null>(null);
  const didSwipeRef = useRef(false);
  const selectedImage = images[selectedImageIndex];
  const hasMultipleImages = images.length > 1;
  const canShowPreviousImage = selectedImageIndex > 0;
  const canShowNextImage = selectedImageIndex < images.length - 1;

  const moveImage = useCallback((direction: 1 | -1, loop = false) => {
    setSelectedImageIndex((currentIndex) => {
      const nextIndex = currentIndex + direction;

      if (loop) {
        return (nextIndex + images.length) % images.length;
      }

      return Math.min(Math.max(nextIndex, 0), images.length - 1);
    });
  }, [images.length]);

  const closeLightbox = useCallback(() => {
    setIsLightboxOpen(false);
    window.requestAnimationFrame(() => mainImageButtonRef.current?.focus());
  }, []);

  useEffect(() => {
    if (!isLightboxOpen) {
      return undefined;
    }

    const previousBodyOverflow = document.body.style.overflow;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        closeLightbox();
      } else if (hasMultipleImages && event.key === "ArrowLeft") {
        event.preventDefault();
        moveImage(-1);
      } else if (hasMultipleImages && event.key === "ArrowRight") {
        event.preventDefault();
        moveImage(1);
      }
    };

    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", handleKeyDown);
    closeButtonRef.current?.focus();

    return () => {
      document.body.style.overflow = previousBodyOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [closeLightbox, hasMultipleImages, isLightboxOpen, moveImage]);

  const handleMainImageClick = () => {
    if (didSwipeRef.current) {
      didSwipeRef.current = false;
      return;
    }

    setIsLightboxOpen(true);
  };

  const handlePointerDown = (event: PointerEvent<HTMLButtonElement>) => {
    if (event.pointerType !== "touch") {
      return;
    }

    didSwipeRef.current = false;
    swipeStartRef.current = {
      pointerId: event.pointerId,
      x: event.clientX,
      y: event.clientY,
    };
  };

  const handlePointerUp = (event: PointerEvent<HTMLButtonElement>) => {
    const swipeStart = swipeStartRef.current;
    swipeStartRef.current = null;

    if (!swipeStart || swipeStart.pointerId !== event.pointerId) {
      return;
    }

    const horizontalDistance = event.clientX - swipeStart.x;
    const verticalDistance = event.clientY - swipeStart.y;

    if (
      Math.abs(horizontalDistance) < SWIPE_THRESHOLD_PX
      || Math.abs(horizontalDistance) <= Math.abs(verticalDistance)
    ) {
      return;
    }

    didSwipeRef.current = true;
    moveImage(horizontalDistance < 0 ? 1 : -1);
  };

  return (
    <section aria-label={`Imágenes de ${toolName}`} className={styles.gallery}>
      <div className={styles.mainImageStage}>
        <button
          aria-label={`Abrir visor de imágenes de ${toolName}`}
          className={styles.mainImageButton}
          onClick={handleMainImageClick}
          onPointerCancel={() => { swipeStartRef.current = null; }}
          onPointerDown={handlePointerDown}
          onPointerUp={handlePointerUp}
          ref={mainImageButtonRef}
          type="button"
        >
          {/* Cloudinary supplies a public HTTPS URL; no remote image config is needed. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img alt={imageAlt} className={styles.mainImage} src={selectedImage.url} />
        </button>

        {hasMultipleImages && canShowPreviousImage && (
          <button
            aria-label="Imagen anterior"
            className={`${styles.mainImageNavigation} ${styles.mainImagePrevious}`}
            onClick={() => moveImage(-1)}
            type="button"
          >
            <ChevronIcon direction="previous" />
          </button>
        )}
        {hasMultipleImages && canShowNextImage && (
          <button
            aria-label="Imagen siguiente"
            className={`${styles.mainImageNavigation} ${styles.mainImageNext}`}
            onClick={() => moveImage(1)}
            type="button"
          >
            <ChevronIcon direction="next" />
          </button>
        )}
      </div>

      {hasMultipleImages && (
        <ul aria-label="Seleccionar imagen" className={styles.thumbnailList}>
          {images.map((image, index) => {
            const isSelected = index === selectedImageIndex;

            return (
              <li key={`${image.position}-${image.url}`}>
                <button
                  aria-current={isSelected ? "true" : undefined}
                  aria-label={`Ver imagen ${index + 1} de ${images.length}`}
                  className={styles.thumbnailButton}
                  data-selected={isSelected}
                  onClick={() => setSelectedImageIndex(index)}
                  type="button"
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img alt="" src={image.url} />
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {isLightboxOpen && (
        <div
          aria-label="Visor de imágenes"
          aria-modal="true"
          className={styles.lightbox}
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              closeLightbox();
            }
          }}
          role="dialog"
        >
          <div className={styles.lightboxContent}>
            <button
              aria-label="Cerrar visor"
              className={styles.closeButton}
              onClick={closeLightbox}
              ref={closeButtonRef}
              type="button"
            >
              <span aria-hidden="true">×</span>
            </button>

            <div className={styles.lightboxMedia}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img alt={imageAlt} className={styles.lightboxImage} src={selectedImage.url} />
            </div>

            {hasMultipleImages && (
              <>
                <button
                  aria-label="Ver imagen anterior"
                  className={`${styles.lightboxNavigation} ${styles.previousButton}`}
                  onClick={() => moveImage(-1, true)}
                  type="button"
                >
                  <span aria-hidden="true">←</span>
                </button>
                <button
                  aria-label="Ver imagen siguiente"
                  className={`${styles.lightboxNavigation} ${styles.nextButton}`}
                  onClick={() => moveImage(1, true)}
                  type="button"
                >
                  <span aria-hidden="true">→</span>
                </button>
                <p className={styles.counter}>{selectedImageIndex + 1} / {images.length}</p>
              </>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
