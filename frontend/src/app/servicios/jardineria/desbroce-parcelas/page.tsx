import type { Metadata } from "next";
import Link from "next/link";

import styles from "./page.module.css";

const approach = [
  {
    title: "Valorar el espacio",
    description:
      "Cada parcela o zona exterior se valora según las características del espacio y la necesidad planteada.",
  },
  {
    title: "Plantear la actuación",
    description:
      "La actuación se plantea de acuerdo con el estado y las necesidades del terreno.",
  },
  {
    title: "Trabajar de forma ordenada",
    description:
      "El trabajo se organiza de forma clara para abordar la consulta de manera práctica.",
  },
];

export const metadata: Metadata = {
  title: "Desbroce de parcelas en Ciudad Real | AUREA",
  description:
    "Desbroce de parcelas y control de maleza en Ciudad Real capital y provincia. Contacta con AUREA y cuéntanos qué necesitas para tu terreno.",
  alternates: { canonical: "/servicios/jardineria/desbroce-parcelas" },
};

function GardenVisual() {
  return (
    <div aria-hidden="true" className={styles.heroVisual}>
      <span className={styles.visualSun} />
      <span className={styles.visualStem} />
      <span className={`${styles.visualLeaf} ${styles.leafLeft}`} />
      <span className={`${styles.visualLeaf} ${styles.leafRight}`} />
      <span className={styles.visualGround} />
      <span className={styles.visualLabel}>Desbroce de parcelas</span>
    </div>
  );
}

export default function ParcelClearingPage() {
  return (
    <div className={styles.page}>
      <main className={styles.main}>
        <nav aria-label="Migas de pan" className={styles.breadcrumbs}>
          <ol>
            <li><Link href="/servicios">Servicios</Link></li>
            <li><Link href="/servicios/jardineria">Jardinería</Link></li>
            <li aria-current="page">Desbroce de parcelas</li>
          </ol>
        </nav>

        <section aria-labelledby="parcel-clearing-title" className={styles.hero}>
          <div className={styles.heroCopy}>
            <p className={styles.eyebrow}>Desbroce de parcelas</p>
            <h1 id="parcel-clearing-title">Desbroce de parcelas en Ciudad Real</h1>
            <p className={styles.intro}>
              AUREA realiza trabajos de desbroce de parcelas y control de maleza en Ciudad Real capital y provincia. Cuéntanos las características del terreno y qué necesitas para poder valorar la actuación.
            </p>
            <div className={styles.heroActions}>
              <Link className={styles.primaryAction} href="/contacto">Cuéntanos qué necesitas</Link>
              <Link className={styles.secondaryAction} href="/servicios/jardineria">Ver servicios de jardinería</Link>
            </div>
          </div>
          <GardenVisual />
        </section>

        <section aria-labelledby="context-title" className={styles.context}>
          <div>
            <p className={styles.eyebrow}>Espacios exteriores</p>
            <h2 id="context-title">Desbroce para parcelas y zonas exteriores</h2>
          </div>
          <p>
            Las parcelas y zonas exteriores pueden acumular vegetación y maleza con el paso del tiempo y requerir una actuación para mantener o preparar el espacio.
          </p>
        </section>

        <section aria-labelledby="service-title" className={styles.service}>
          <div className={styles.sectionHeading}>
            <p className={styles.eyebrow}>Jardinería AUREA</p>
            <h2 id="service-title">Desbroce y control de maleza</h2>
          </div>
          <p>
            AUREA realiza trabajos de desbroce y control de maleza, adaptando la actuación a las características del terreno y de la zona exterior.
          </p>
        </section>

        <section aria-labelledby="anticipation-title" className={styles.anticipation}>
          <div>
            <p className={styles.eyebrow}>Actuar con antelación</p>
            <h2 id="anticipation-title">Preparar el terreno antes de los meses de mayor riesgo</h2>
          </div>
          <p>
            Controlar la acumulación de vegetación y maleza con antelación permite mantener el terreno preparado antes de las épocas de mayor riesgo.
          </p>
        </section>

        <section aria-labelledby="approach-title" className={styles.approach}>
          <div className={styles.sectionHeading}>
            <p className={styles.eyebrow}>Forma de trabajar</p>
            <h2 id="approach-title">Una actuación adaptada a cada espacio</h2>
          </div>
          <div className={styles.approachList}>
            {approach.map((item, index) => (
              <article key={item.title}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <h3>{item.title}</h3>
                <p>{item.description}</p>
              </article>
            ))}
          </div>
          <Link className={styles.gardeningLink} href="/servicios/jardineria">
            Ver todos los servicios de jardinería
          </Link>
        </section>

        <section aria-labelledby="final-title" className={styles.finalCta}>
          <div>
            <p className={styles.eyebrow}>Contacto</p>
            <h2 id="final-title">¿Necesitas desbrozar una parcela?</h2>
            <p>Cuéntanos las características del terreno y qué necesitas para que podamos conocer mejor tu consulta.</p>
          </div>
          <Link className={styles.finalAction} href="/contacto">Contactar con AUREA</Link>
        </section>
      </main>
    </div>
  );
}
