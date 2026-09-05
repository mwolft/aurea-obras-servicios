import type { Metadata } from "next";
import Link from "next/link";

import { getPublicUrl } from "@/lib/site";

import styles from "./page.module.css";

const socialImageUrl = getPublicUrl("/icon.png");
const socialDescription =
  "AUREA Obras y Servicios S.L. reúne jardinería, fontanería, electricidad, obras y reformas, además de alquiler de herramientas.";

export const metadata: Metadata = {
  title: "AUREA Obras y Servicios S.L. | Servicios y alquiler de herramientas",
  description: socialDescription,
  alternates: { canonical: "/" },
  openGraph: {
    title: "AUREA Obras y Servicios S.L.",
    description: socialDescription,
    url: getPublicUrl(),
    type: "website",
    images: [{ url: socialImageUrl, width: 1536, height: 1024, alt: "Icono de AUREA" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "AUREA Obras y Servicios S.L.",
    description: socialDescription,
    images: [socialImageUrl],
  },
};

function ServicesIcon() {
  return <svg aria-hidden="true" viewBox="0 0 48 48"><path d="M8 39h32M14 39V18l10-8 10 8v21M20 39V27h8v12M10 18h28" /></svg>;
}

function GardenIcon() {
  return <svg aria-hidden="true" viewBox="0 0 48 48"><path d="M24 40V24M24 30c-9 0-13-6-13-13 9 0 13 6 13 13ZM24 25c0-9 5-14 13-15 0 9-5 14-13 15ZM14 40h20" /></svg>;
}

function ToolsIcon() {
  return <svg aria-hidden="true" viewBox="0 0 48 48"><path d="m31 10 7 7-9 9-7-7 9-9ZM24 17 10 31l7 7 14-14M11 12l7 7m-8 0 9-9" /></svg>;
}

export default function Home() {
  return (
    <div className={styles.page}>
      <main className={styles.main}>
        <section aria-labelledby="hero-title" className={styles.hero}>
          <div className={styles.heroCopy}>
            <p className={styles.eyebrow}>AUREA · SERVICIOS · ALQUILER</p>
            <h1 id="hero-title">Soluciones para cada proyecto.</h1>
            <p className={styles.intro}>
              Jardinería, fontanería, electricidad y obras y reformas. También contamos con alquiler de herramientas para cuando las necesitas.
            </p>
            <div className={styles.heroActions}>
              <Link className={styles.primaryAction} href="/servicios/jardineria">
                Conocer Jardinería
              </Link>
              <Link className={styles.secondaryAction} href="/alquiler">Ver alquiler</Link>
            </div>
          </div>

          <div aria-hidden="true" className={styles.heroVisual}>
            <span className={styles.visualLabel}>Servicios · Jardinería · Alquiler</span>
            <div className={styles.heroMark}><GardenIcon /></div>
            <span className={`${styles.heroLine} ${styles.heroLineOne}`} />
            <span className={`${styles.heroLine} ${styles.heroLineTwo}`} />
            <span className={`${styles.heroBlock} ${styles.heroBlockOne}`} />
            <span className={`${styles.heroBlock} ${styles.heroBlockTwo}`} />
          </div>
        </section>

        <section aria-labelledby="services-title" className={styles.services}>
          <div className={styles.sectionHeading}>
            <p className={styles.eyebrow}>Áreas de servicio</p>
            <h2 id="services-title">Una empresa multiservicio para distintas necesidades.</h2>
          </div>
          <div className={styles.serviceGrid}>
            <article className={`${styles.serviceCard} ${styles.gardenCard}`}>
              <div className={styles.icon}><GardenIcon /></div>
              <h3>Jardinería</h3>
              <p>Un área destacada de AUREA para preparar y cuidar espacios exteriores.</p>
              <Link className={styles.cardLink} href="/servicios/jardineria">
                Ver servicios de jardinería <span aria-hidden="true">→</span>
              </Link>
            </article>
            <article className={styles.serviceCard}>
              <div className={styles.icon}><ServicesIcon /></div>
              <h3>Fontanería</h3>
              <p>Una de las áreas de servicio de AUREA.</p>
            </article>
            <article className={styles.serviceCard}>
              <div className={styles.icon}><ServicesIcon /></div>
              <h3>Electricidad</h3>
              <p>Una de las áreas de servicio de AUREA.</p>
            </article>
            <article className={styles.serviceCard}>
              <div className={styles.icon}><ServicesIcon /></div>
              <h3>Obras y reformas</h3>
              <p>Una de las áreas de servicio de AUREA.</p>
            </article>
          </div>
          <Link className={styles.servicesAction} href="/servicios">Ver todos los servicios</Link>
        </section>

        <section aria-labelledby="gardening-title" className={styles.gardeningFeature}>
          <div aria-hidden="true" className={styles.gardeningVisual}><GardenIcon /></div>
          <div>
            <p className={styles.eyebrow}>Jardinería</p>
            <h2 id="gardening-title">Cuidar, despejar y preparar los espacios exteriores.</h2>
            <p>Desbroce de parcelas y maleza, jardines de urbanizaciones y mini excavaciones vinculadas a jardín.</p>
            <Link className={styles.primaryAction} href="/servicios/jardineria">Ver servicios de jardinería</Link>
          </div>
        </section>

        <section aria-labelledby="winter-title" className={styles.editorial}>
          <p className={styles.eyebrow}>Trabajo anticipado</p>
          <blockquote>“Los fuegos se apagan en invierno”.</blockquote>
          <div>
            <h2 id="winter-title">Preparar los espacios antes de los meses de mayor riesgo.</h2>
            <p>El trabajo realizado con antelación permite limpiar, desbrozar y preparar parcelas y zonas exteriores con tiempo.</p>
          </div>
        </section>

        <section aria-labelledby="multiservice-title" className={styles.multiservice}>
          <div>
            <p className={styles.eyebrow}>Más allá de Jardinería</p>
            <h2 id="multiservice-title">AUREA reúne servicios para distintos proyectos.</h2>
          </div>
          <p>Fontanería, electricidad y obras y reformas completan una oferta multiservicio junto a Jardinería.</p>
        </section>

        <section aria-labelledby="rental-title" className={styles.rental}>
          <div aria-hidden="true" className={styles.rentalIcon}><ToolsIcon /></div>
          <div>
            <p className={styles.eyebrow}>Alquiler</p>
            <h2 id="rental-title">Herramientas para cuando quieres hacer tu propio proyecto.</h2>
            <p>Si buscas que AUREA realice un trabajo, explora nuestros servicios. Si necesitas herramientas, consulta el catálogo de alquiler.</p>
          </div>
          <Link className={styles.secondaryAction} href="/alquiler">Ver herramientas en alquiler</Link>
        </section>

        <section aria-labelledby="contact-title" className={styles.contactCta}>
          <div>
            <p className={styles.eyebrow}>Contacto</p>
            <h2 id="contact-title">Cuéntanos qué necesitas.</h2>
            <p>Comparte tu proyecto con AUREA y te orientaremos hacia el área de servicio adecuada.</p>
          </div>
          <Link className={styles.primaryAction} href="/contacto">Ir a Contacto</Link>
        </section>
      </main>
    </div>
  );
}
