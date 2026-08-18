import type { Metadata } from "next";

import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "AUREA Obras y Servicios | Obras, jardinería y alquiler de herramientas",
  description:
    "AUREA Obras y Servicios prepara soluciones para obras y reformas, jardinería y alquiler de herramientas.",
};

export default function Home() {
  return (
    <div className={styles.page}>
      <header className={styles.navbar}>
        <span className={styles.brand}>AUREA Obras y Servicios</span>
        <span className={styles.navStatus}>Próximamente</span>
      </header>

      <main className={styles.main}>
        <section className={styles.hero} aria-labelledby="hero-title">
          <div className={styles.copy}>
            <p className={styles.eyebrow}>En construcción</p>
            <h1 id="hero-title">Estamos construyendo algo sólido.</h1>
            <p className={styles.intro}>
              AUREA Obras y Servicios prepara una forma cercana y práctica de encontrar apoyo para
              obras y reformas, jardinería y alquiler de herramientas.
            </p>
            <p className={styles.comingSoon}>Muy pronto compartiremos más novedades.</p>
          </div>

          <div className={styles.constructionMark} aria-hidden="true">
            <div className={styles.spinner} />
            <div className={styles.bricks}>
              <span />
              <span />
              <span />
              <span />
            </div>
          </div>
        </section>

        <section className={styles.services} aria-labelledby="services-title">
          <p className={styles.eyebrow}>Lo que estamos preparando</p>
          <h2 id="services-title">Servicios pensados para poner manos a la obra</h2>
          <ul className={styles.serviceList}>
            <li>Obras y reformas</li>
            <li>Jardinería</li>
            <li>Alquiler de herramientas</li>
          </ul>
        </section>
      </main>

      <footer className={styles.footer}>© {new Date().getFullYear()} AUREA Obras y Servicios</footer>
    </div>
  );
}
