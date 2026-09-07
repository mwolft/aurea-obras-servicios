import Link from "next/link";

import { businessProfile } from "@/lib/business-profile";
import { CookiePreferencesButton } from "@/components/cookie-preferences-button";
import { LocationIcon, PhoneIcon } from "@/components/icons";

import styles from "./site-footer.module.css";

export function SiteFooter() {
  return (
    <footer className={styles.footer}>
      <div className={styles.content}>
        <div className={styles.primaryRow}>
          <div className={styles.brandBlock}>
            <span aria-hidden="true" className={styles.accent} />
            <p className={styles.name}>{businessProfile.name}</p>
            <div className={styles.locationDetails}>
              <p className={styles.locationCity}>
                <LocationIcon className={styles.infoIcon} />
                <span>{businessProfile.location.city}</span>
              </p>
              <p>
                {businessProfile.location.lineOne}
                <br />
                {businessProfile.location.lineTwo}
              </p>
            </div>
          </div>

          <section aria-labelledby="footer-contact" className={styles.footerSection}>
            <h2 id="footer-contact">Contacto</h2>
            <a className={styles.contactLink} href={businessProfile.phoneHref}>
              <PhoneIcon className={styles.infoIcon} />
              <span>{businessProfile.phone}</span>
            </a>
            <Link href="/contacto">Formulario de contacto</Link>
          </section>

          <section aria-labelledby="footer-services" className={styles.footerSection}>
            <h2 id="footer-services">Servicios</h2>
            <nav aria-label="Servicios de AUREA" className={styles.servicesNavigation}>
              <Link href="/servicios/jardineria">Jardinería</Link>
              <Link href="/servicios/fontaneria">Fontanería</Link>
              <Link href="/servicios/electricidad">Electricidad</Link>
              <Link href="/servicios/obras-reformas">Obras y reformas</Link>
            </nav>
          </section>

          <section aria-labelledby="footer-rental" className={styles.footerSection}>
            <h2 id="footer-rental">Alquiler</h2>
            <nav aria-label="Alquiler de AUREA" className={styles.rentalNavigation}>
              <Link href="/alquiler">Alquiler de maquinaria</Link>
              <Link href="/alquiler">Alquiler de herramientas</Link>
            </nav>
          </section>
        </div>

        <nav aria-label="Información legal" className={styles.legalNavigation}>
          <Link href="/aviso-legal">Aviso legal</Link>
          <Link href="/politica-de-privacidad">Política de privacidad</Link>
          <Link href="/politica-de-cookies">Política de cookies</Link>
          <CookiePreferencesButton className={styles.cookiePreferencesButton} />
        </nav>
      </div>
    </footer>
  );
}
