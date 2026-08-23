"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { useAuth } from "./auth-provider";
import styles from "./site-header.module.css";

type NavigationActionsProps = {
  closeMenu: () => void;
  isLoggingOut: boolean;
  onLogout: () => void;
};

function NavigationLinks({ closeMenu }: Pick<NavigationActionsProps, "closeMenu">) {
  const pathname = usePathname();

  const isActive = (href: string) =>
    href === "/" ? pathname === href : pathname === href || pathname.startsWith(`${href}/`);

  return (
    <>
      <Link aria-current={isActive("/") ? "page" : undefined} href="/" onClick={closeMenu}>
        Inicio
      </Link>
      <Link
        aria-current={isActive("/alquiler") ? "page" : undefined}
        href="/alquiler"
        onClick={closeMenu}
      >
        Alquiler
      </Link>
    </>
  );
}

function NavigationActions({ closeMenu, isLoggingOut, onLogout }: NavigationActionsProps) {
  const { isLoading, user } = useAuth();

  if (isLoading) {
    return <span aria-live="polite" className={styles.loading}>Comprobando sesión…</span>;
  }

  if (!user) {
    return (
      <Link className={styles.loginLink} href="/login" onClick={closeMenu}>
        Iniciar sesión
      </Link>
    );
  }

  return (
    <>
      <Link href="/mi-cuenta" onClick={closeMenu}>
        Mi cuenta
      </Link>
      <button disabled={isLoggingOut} onClick={onLogout} type="button">
        {isLoggingOut ? "Cerrando sesión…" : "Cerrar sesión"}
      </button>
    </>
  );
}

export function SiteHeader() {
  const { logout } = useAuth();
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [logoutError, setLogoutError] = useState(false);
  const headerRef = useRef<HTMLElement>(null);
  const pathname = usePathname();
  const router = useRouter();

  const closeMenu = () => {
    setIsMenuOpen(false);
  };

  useEffect(() => {
    if (!isMenuOpen) {
      return;
    }

    const closeOnOutsideInteraction = (event: MouseEvent | TouchEvent) => {
      if (headerRef.current && !headerRef.current.contains(event.target as Node)) {
        setIsMenuOpen(false);
      }
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsMenuOpen(false);
      }
    };

    document.addEventListener("mousedown", closeOnOutsideInteraction);
    document.addEventListener("touchstart", closeOnOutsideInteraction);
    document.addEventListener("keydown", closeOnEscape);

    return () => {
      document.removeEventListener("mousedown", closeOnOutsideInteraction);
      document.removeEventListener("touchstart", closeOnOutsideInteraction);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [isMenuOpen]);

  const handleLogout = async () => {
    setLogoutError(false);
    setIsLoggingOut(true);
    const didLogout = await logout();
    setIsLoggingOut(false);
    closeMenu();

    if (!didLogout) {
      setLogoutError(true);
      return;
    }

    if (pathname === "/mi-cuenta") {
      router.replace("/");
    }
  };

  return (
    <header className={styles.header} ref={headerRef}>
      <div className={styles.content}>
        <Link className={styles.brand} href="/" onClick={closeMenu}>
          AUREA Obras y Servicios S.L.
        </Link>

        <nav aria-label="Navegación principal" className={styles.desktopNavigation}>
          <NavigationLinks closeMenu={closeMenu} />
          <NavigationActions
            closeMenu={closeMenu}
            isLoggingOut={isLoggingOut}
            onLogout={handleLogout}
          />
        </nav>

        <button
          aria-controls="mobile-navigation"
          aria-expanded={isMenuOpen}
          aria-label={isMenuOpen ? "Cerrar menú de navegación" : "Abrir menú de navegación"}
          className={styles.menuButton}
          onClick={() => setIsMenuOpen((isOpen) => !isOpen)}
          type="button"
        >
          <span aria-hidden="true" className={styles.menuIcon}>
            <span />
            <span />
            <span />
          </span>
        </button>
      </div>

      <div className={styles.mobileMenu} hidden={!isMenuOpen} id="mobile-navigation">
        <nav aria-label="Navegación móvil" className={styles.mobileNavigation}>
          <NavigationLinks closeMenu={closeMenu} />
          <NavigationActions
            closeMenu={closeMenu}
            isLoggingOut={isLoggingOut}
            onLogout={handleLogout}
          />
        </nav>
      </div>

      {logoutError ? (
        <p className={styles.error} role="alert">
          No se ha podido cerrar la sesión. Inténtalo de nuevo.
        </p>
      ) : null}
    </header>
  );
}
