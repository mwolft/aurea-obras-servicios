import Link from "next/link";

import { businessProfile } from "@/lib/business-profile";
import { CookiePreferencesButton } from "@/components/cookie-preferences-button";

import styles from "./site-footer.module.css";

export function SiteFooter() {
  return (
    <footer className={styles.footer}>
      <div className={styles.content}>
        <div className={styles.brandBlock}>
          <span aria-hidden="true" className={styles.accent} />
          <p className={styles.name}>{businessProfile.name}</p>
          <p className={styles.description}>
            Obras, reformas, jardinería y alquiler de herramientas.
          </p>
        </div>

        <section aria-labelledby="footer-contact" className={styles.footerSection}>
          <h2 id="footer-contact">Contacto</h2>
          <a className={styles.contactLink} href={businessProfile.phoneHref}>{businessProfile.phone}</a>
          <Link href="/contacto">Formulario de contacto</Link>
        </section>

        <section aria-labelledby="footer-location" className={styles.footerSection}>
          <h2 id="footer-location">Ubicación</h2>
          <p>{businessProfile.location.city}</p>
          <p>{businessProfile.location.lineOne}<br />{businessProfile.location.lineTwo}</p>
          <a href={businessProfile.location.mapsUrl} rel="noreferrer" target="_blank">Abrir en Google Maps</a>
        </section>

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
