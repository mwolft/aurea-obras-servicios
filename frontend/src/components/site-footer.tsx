import Link from "next/link";

import { CookiePreferencesButton } from "@/components/cookie-preferences-button";
import { legalInfo } from "@/lib/legal";

import styles from "./site-footer.module.css";

export function SiteFooter() {
  return (
    <footer className={styles.footer}>
      <div className={styles.content}>
        <div>
          <span aria-hidden="true" className={styles.accent} />
          <p className={styles.name}>{legalInfo.companyName}</p>
          <p className={styles.description}>
            Obras, reformas, jardinería y alquiler de herramientas.
          </p>
        </div>

        <div className={styles.navigationGroups}>
          <nav aria-label="Navegación principal del pie de página" className={styles.navigation}>
            <Link href="/">Inicio</Link>
            <Link href="/servicios">Servicios</Link>
            <Link href="/alquiler">Alquiler</Link>
            <Link href="/contacto">Contacto</Link>
          </nav>
          <nav aria-label="Información legal" className={styles.navigation}>
            <Link href="/aviso-legal">Aviso legal</Link>
            <Link href="/politica-de-privacidad">Política de privacidad</Link>
            <Link href="/politica-de-cookies">Política de cookies</Link>
            <CookiePreferencesButton className={styles.cookiePreferencesButton} />
          </nav>
        </div>
      </div>
    </footer>
  );
}
