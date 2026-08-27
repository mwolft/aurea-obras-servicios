import Link from "next/link";

import styles from "./site-footer.module.css";

export function SiteFooter() {
  return (
    <footer className={styles.footer}>
      <div className={styles.content}>
        <div>
          <span aria-hidden="true" className={styles.accent} />
          <p className={styles.name}>AUREA Obras y Servicios S.L.</p>
          <p className={styles.description}>
            Obras, reformas, jardinería y alquiler de herramientas.
          </p>
        </div>

        <nav aria-label="Navegación del pie de página" className={styles.navigation}>
          <Link href="/">Inicio</Link>
          <Link href="/servicios">Servicios</Link>
          <Link href="/alquiler">Alquiler</Link>
          <Link href="/contacto">Contacto</Link>
          <span>Web en desarrollo</span>
        </nav>
      </div>
    </footer>
  );
}
