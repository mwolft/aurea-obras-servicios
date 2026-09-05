import type { Metadata } from "next";
import Link from "next/link";

import styles from "./page.module.css";

const gardeningAreas = [
  {
    title: "Desbroce y maleza",
    description:
      "Trabajos de desbroce y control de maleza para mantener parcelas y zonas exteriores atendidas.",
  },
  {
    title: "Jardines de urbanizaciones",
    description:
      "Atención a jardines y espacios comunes de urbanizaciones dentro de la línea de jardinería de AUREA.",
  },
  {
    title: "Mini excavaciones",
    description:
      "Trabajos auxiliares y movimientos puntuales donde el uso de maquinaria compacta resulta adecuado para el jardín.",
  },
];

export const metadata: Metadata = {
  title: "Jardinería | AUREA Obras y Servicios S.L.",
  description:
    "Jardinería en AUREA: desbroce y maleza, jardines de urbanizaciones y mini excavaciones vinculadas a espacios exteriores.",
  alternates: { canonical: "/servicios/jardineria" },
};

function GardenLineIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 48 48">
      <path d="M24 41V25M24 31c-10 0-14-6-14-14 9 0 14 6 14 14ZM24 25c0-9 5-15 14-16 0 10-5 15-14 16ZM12 41h24" />
    </svg>
  );
}

export default function GardeningPage() {
  return (
    <div className={styles.page}>
      <main className={styles.main}>
        <section aria-labelledby="gardening-title" className={styles.hero}>
          <div className={styles.heroCopy}>
            <p className={styles.eyebrow}>Jardinería</p>
            <h1 id="gardening-title">Jardinería para terrenos, jardines y zonas exteriores.</h1>
            <p className={styles.intro}>
              AUREA realiza trabajos de jardinería y mantenimiento de terrenos desde una perspectiva práctica, adaptada a las necesidades de cada espacio.
            </p>
            <div className={styles.heroActions}>
              <Link className={styles.primaryAction} href="/contacto">Cuéntanos qué necesitas</Link>
              <Link className={styles.secondaryAction} href="/servicios">Ver todos los servicios</Link>
            </div>
          </div>

          <div aria-hidden="true" className={styles.heroVisual}>
            <div className={styles.visualSun} />
            <div className={styles.visualStem} />
            <div className={`${styles.visualLeaf} ${styles.leafLeft}`} />
            <div className={`${styles.visualLeaf} ${styles.leafRight}`} />
            <div className={styles.visualGround} />
            <span className={styles.visualLabel}>Jardinería AUREA</span>
          </div>
        </section>

        <section aria-labelledby="presentation-title" className={styles.presentation}>
          <div>
            <p className={styles.eyebrow}>Enfoque práctico</p>
            <h2 id="presentation-title">Cada espacio necesita una actuación adecuada.</h2>
          </div>
          <p>
            Valoramos el terreno, la vegetación y el tipo de trabajo para plantear una actuación ordenada y ajustada a la necesidad concreta.
          </p>
        </section>

        <section aria-labelledby="services-title" className={styles.services} id="servicios-jardineria">
          <div className={styles.sectionHeading}>
            <p className={styles.eyebrow}>Líneas de trabajo</p>
            <h2 id="services-title">Jardinería para mantener y preparar espacios exteriores.</h2>
            <p>Estas son las principales líneas de trabajo de AUREA dentro de Jardinería.</p>
          </div>
          <div className={styles.serviceGrid}>
            {gardeningAreas.map((service) => (
              <article className={styles.serviceCard} key={service.title}>
                <div className={styles.serviceIcon}><GardenLineIcon /></div>
                <h3>{service.title}</h3>
                <p>{service.description}</p>
              </article>
            ))}
          </div>
        </section>

        <section aria-labelledby="winter-title" className={styles.winter}>
          <div>
            <p className={styles.eyebrow}>Trabajar con antelación</p>
            <h2 id="winter-title">Los fuegos se apagan en invierno.</h2>
          </div>
          <div className={styles.winterCopy}>
            <p>
              Mantener el terreno, desbrozar y reducir la acumulación de vegetación con antelación ayuda a preparar los espacios antes de los meses de mayor riesgo.
            </p>
            <Link className={styles.winterAction} href="/contacto">Contactar con AUREA</Link>
          </div>
        </section>

        <section aria-labelledby="approach-title" className={styles.approach}>
          <div className={styles.sectionHeading}>
            <p className={styles.eyebrow}>Cómo trabaja AUREA</p>
            <h2 id="approach-title">Una actuación ordenada para cada necesidad.</h2>
            <p>
              El trabajo se plantea según las características del espacio y los medios adecuados para llevarlo a cabo.
            </p>
          </div>
          <div className={styles.approachList}>
            <article>
              <h3>Valorar el espacio</h3>
              <p>Atender las características del terreno o jardín antes de plantear el trabajo.</p>
            </article>
            <article>
              <h3>Elegir los medios adecuados</h3>
              <p>Adaptar la actuación a las necesidades concretas de cada zona exterior.</p>
            </article>
            <article>
              <h3>Trabajar de forma ordenada</h3>
              <p>Coordinar el trabajo para abordar cada consulta de manera práctica.</p>
            </article>
          </div>
        </section>

        <section aria-labelledby="final-title" className={styles.finalCta}>
          <div>
            <p className={styles.eyebrow}>Contacto</p>
            <h2 id="final-title">Cuéntanos qué necesitas para tu espacio exterior.</h2>
            <p>Explícanos el trabajo que necesitas y podremos conocer mejor tu consulta.</p>
          </div>
          <Link className={styles.finalAction} href="/contacto">Contactar con AUREA</Link>
        </section>
      </main>
    </div>
  );
}
