import type { Metadata } from "next";
import Link from "next/link";

import styles from "./page.module.css";

const serviceAreas = [
  {
    name: "Fontanería",
    description:
      "Una de las áreas de trabajo que forman parte de la oferta multiservicio de AUREA.",
  },
  {
    name: "Electricidad",
    description:
      "Servicios de electricidad integrados en la propuesta de trabajo de AUREA.",
  },
  {
    name: "Obras / Reformas",
    description:
      "Trabajos de obras y reformas dentro de las áreas de servicio de AUREA.",
  },
];

export const metadata: Metadata = {
  title: "Servicios | AUREA Obras y Servicios S.L.",
  description:
    "AUREA Obras y Servicios S.L. reúne jardinería, fontanería, electricidad y obras y reformas, junto a alquiler de herramientas.",
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
          <h1 id="services-title">Soluciones para trabajos, mantenimiento y actuaciones.</h1>
          <p className={styles.intro}>
            AUREA reúne distintos servicios para viviendas, terrenos e instalaciones. Cuéntanos qué necesitas y valoraremos la mejor forma de ayudarte.
          </p>
          <div className={styles.heroActions}>
            <Link className={styles.primaryAction} href="/contacto">
              Cuéntanos qué necesitas
            </Link>
            <Link className={styles.secondaryAction} href="/servicios/jardineria">
              Conocer Jardinería
            </Link>
          </div>
        </section>

        <section aria-labelledby="gardening-title" className={styles.featuredService}>
          <div className={styles.featuredCopy}>
            <p className={styles.eyebrow}>Área destacada</p>
            <h2 id="gardening-title">Jardinería</h2>
            <p>
              Una línea protagonista de AUREA para el cuidado y la preparación de espacios exteriores, con atención a parcelas, zonas comunes y trabajos vinculados al jardín.
            </p>
            <ul className={styles.gardeningList}>
              <li>Desbroce de parcelas y maleza</li>
              <li>Jardines de urbanizaciones</li>
              <li>Mini excavaciones vinculadas a jardín</li>
            </ul>
            <Link className={styles.primaryAction} href="/servicios/jardineria">
              Ver servicios de jardinería
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

        <section aria-labelledby="service-areas-title" className={styles.serviceAreas}>
          <div className={styles.sectionHeading}>
            <p className={styles.eyebrow}>Áreas de AUREA</p>
            <h2 id="service-areas-title">Una empresa multiservicio.</h2>
            <p>
              Además de Jardinería, AUREA ofrece Fontanería, Electricidad y Obras / Reformas como parte de sus áreas de trabajo.
            </p>
          </div>
          <div className={styles.areasGrid}>
            {serviceAreas.map((service, index) => (
              <article className={styles.serviceCard} key={service.name}>
                <span className={styles.cardNumber}>{String(index + 2).padStart(2, "0")}</span>
                <h3>{service.name}</h3>
                <p>{service.description}</p>
              </article>
            ))}
          </div>
        </section>

        <section aria-labelledby="closing-title" className={styles.closing}>
          <p className={styles.eyebrow}>Contacto</p>
          <h2 id="closing-title">¿Necesitas alguno de estos servicios?</h2>
          <p>
            Explícanos qué trabajo necesitas y podremos conocer mejor tu consulta.
          </p>
          <Link className={styles.closingAction} href="/contacto">
            Contactar con AUREA
          </Link>
        </section>
      </main>
    </div>
  );
}
