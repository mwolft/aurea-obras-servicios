import type { Metadata } from "next";
import Link from "next/link";

import styles from "./page.module.css";

// TODO: sustituir por contenido confirmado por Emilio.
const provisionalGardeningServices = [
  {
    title: "Mantenimiento de jardines",
    description: "Una propuesta orientada al cuidado continuado de espacios exteriores.",
  },
  {
    title: "Cuidado de zonas verdes",
    description: "Atención general para conservar y acompañar cada espacio según su necesidad.",
  },
  {
    title: "Espacios exteriores",
    description: "Soluciones de jardinería que iremos detallando con la información definitiva.",
  },
  {
    title: "Atención personalizada",
    description: "Cada consulta parte de las características concretas del espacio a cuidar.",
  },
];

export const metadata: Metadata = {
  title: "Jardinería | AUREA Obras y Servicios S.L.",
  description:
    "AUREA Obras y Servicios S.L. ofrece servicios de jardinería y prepara información detallada sobre esta línea de trabajo.",
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
            <h1 id="gardening-title">Espacios exteriores atendidos con cercanía.</h1>
            <p className={styles.intro}>
              AUREA incorpora la jardinería como una línea importante de su trabajo. Estamos preparando la información completa para presentar cada servicio con claridad.
            </p>
            <Link className={styles.primaryAction} href="/contacto">Solicitar información</Link>
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
            <p className={styles.eyebrow}>Una línea de trabajo cercana</p>
            <h2 id="presentation-title">Jardinería para cuidar cada espacio exterior.</h2>
          </div>
          <p>
            Abordamos trabajos de jardinería y mantenimiento de espacios exteriores desde una atención directa y adaptada a cada necesidad. Los detalles de la propuesta se incorporarán a medida que se concreten.
          </p>
        </section>

        <section aria-labelledby="services-title" className={styles.services} id="servicios-jardineria">
          <div className={styles.sectionHeading}>
            <p className={styles.eyebrow}>Servicios de jardinería</p>
            <h2 id="services-title">Una base preparada para crecer con información concreta.</h2>
            <p>Estamos terminando de definir el alcance de cada servicio junto a Emilio.</p>
          </div>
          <div className={styles.serviceGrid}>
            {provisionalGardeningServices.map((service) => (
              <article className={styles.serviceCard} key={service.title}>
                <div className={styles.serviceIcon}><GardenLineIcon /></div>
                <h3>{service.title}</h3>
                <p>{service.description}</p>
              </article>
            ))}
          </div>
        </section>

        <section aria-labelledby="approach-title" className={styles.approach}>
          <div>
            <p className={styles.eyebrow}>Nuestro enfoque</p>
            <h2 id="approach-title">Atención directa para cada necesidad.</h2>
          </div>
          <ul>
            <li>Atención cercana desde el primer contacto.</li>
            <li>Trabajo adaptado a las características de cada espacio.</li>
            <li>Coordinación directa para plantear cada consulta.</li>
          </ul>
        </section>

        <section aria-labelledby="projects-title" className={styles.projects}>
          <div className={styles.sectionHeading}>
            <p className={styles.eyebrow}>Próximamente</p>
            <h2 id="projects-title">Trabajos e imágenes que mostrarán la propuesta completa.</h2>
            <p>Estamos preparando esta sección con información y fotografías reales.</p>
          </div>
          <div aria-hidden="true" className={styles.placeholderGrid}>
            <div className={`${styles.placeholder} ${styles.placeholderTall}`} />
            <div className={styles.placeholder} />
            <div className={styles.placeholder} />
          </div>
        </section>

        <section aria-labelledby="final-title" className={styles.finalCta}>
          <div>
            <p className={styles.eyebrow}>Jardinería AUREA</p>
            <h2 id="final-title">Estamos preparando toda la información para ayudarte a valorar tu necesidad.</h2>
            <p>Próximamente incorporaremos los detalles de esta línea de servicio.</p>
          </div>
          <span className={styles.ctaStatus}>Contenido en preparación</span>
        </section>
      </main>
    </div>
  );
}
