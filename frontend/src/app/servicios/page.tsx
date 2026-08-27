import type { Metadata } from "next";
import Link from "next/link";

import styles from "./page.module.css";

// TODO: sustituir estas áreas provisionales por los servicios confirmados por Emilio.
const provisionalServices = [
  "Próximo servicio",
  "Nueva área de servicio",
  "Información en preparación",
];

export const metadata: Metadata = {
  title: "Servicios | AUREA Obras y Servicios S.L.",
  description:
    "Conoce las áreas de servicio de AUREA Obras y Servicios S.L. Estamos ampliando la información de nuestra oferta comercial.",
  alternates: { canonical: "/servicios" },
};

function GardenIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 48 48">
      <path d="M24 41V25M24 31c-10 0-14-6-14-14 9 0 14 6 14 14ZM24 25c0-9 5-15 14-16 0 10-5 15-14 16ZM12 41h24" />
    </svg>
  );
}

export default function ServicesPage() {
  return (
    <div className={styles.page}>
      <main className={styles.main}>
        <section aria-labelledby="services-title" className={styles.hero}>
          <p className={styles.eyebrow}>Servicios</p>
          <h1 id="services-title">Áreas de trabajo que iremos presentando con claridad.</h1>
          <p className={styles.intro}>
            AUREA Obras y Servicios S.L. está preparando la información de sus líneas de trabajo para que cada consulta encuentre un punto de partida sencillo y útil.
          </p>
        </section>

        <section aria-labelledby="gardening-title" className={styles.featuredService}>
          <div className={styles.featuredCopy}>
            <p className={styles.eyebrow}>Área destacada</p>
            <h2 id="gardening-title">Jardinería</h2>
            <p>
              Una línea importante de AUREA, orientada a trabajos de jardinería y al cuidado de espacios exteriores. Ya puedes conocer la propuesta que estamos preparando.
            </p>
            <Link className={styles.primaryAction} href="/servicios/jardineria">
              Ver jardinería
            </Link>
          </div>
          <div aria-hidden="true" className={styles.featuredVisual}>
            <div className={styles.sun} />
            <div className={styles.stem} />
            <div className={`${styles.leaf} ${styles.leafLeft}`} />
            <div className={`${styles.leaf} ${styles.leafRight}`} />
            <div className={styles.ground} />
            <div className={styles.gardenIcon}>
              <GardenIcon />
            </div>
          </div>
        </section>

        <section aria-labelledby="future-services-title" className={styles.futureServices}>
          <div className={styles.sectionHeading}>
            <p className={styles.eyebrow}>En preparación</p>
            <h2 id="future-services-title">Nuevas áreas de servicio, próximamente.</h2>
            <p>
              Incorporaremos cada área cuando dispongamos de información confirmada y útil para explicarla correctamente.
            </p>
          </div>
          <div className={styles.provisionalGrid}>
            {provisionalServices.map((service, index) => (
              <article className={styles.provisionalCard} key={service}>
                <span className={styles.cardNumber}>{String(index + 1).padStart(2, "0")}</span>
                <h3>{service}</h3>
                <p>Contenido comercial pendiente de incorporación.</p>
              </article>
            ))}
          </div>
        </section>

        <section aria-labelledby="closing-title" className={styles.closing}>
          <p className={styles.eyebrow}>AUREA</p>
          <h2 id="closing-title">Estamos ampliando la información de nuestras áreas de trabajo.</h2>
          <p>
            Esta sección irá creciendo de forma progresiva, con contenidos concretos para ayudarte a conocer mejor cada propuesta.
          </p>
        </section>
      </main>
    </div>
  );
}
