import type { Metadata } from "next";
import { IBM_Plex_Sans } from "next/font/google";
import Link from "next/link";

import { getPublicUrl, siteUrl } from "@/lib/site";

import styles from "./page.module.css";

const ibmPlexSans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

const socialImageUrl = `${siteUrl}/brand/aurea-social.png`;
const socialDescription =
  "AUREA Obras y Servicios S.L. prepara soluciones para obras y reformas, jardinería y alquiler de herramientas.";

export const metadata: Metadata = {
  title: "AUREA Obras y Servicios S.L. | Obras, jardinería y alquiler de herramientas",
  description: socialDescription,
  alternates: { canonical: "/" },
  openGraph: {
    title: "AUREA Obras y Servicios S.L.",
    description: socialDescription,
    url: getPublicUrl(),
    type: "website",
    images: [{ url: socialImageUrl, width: 1200, height: 630, alt: "AUREA Obras y Servicios S.L." }],
  },
  twitter: {
    card: "summary_large_image",
    title: "AUREA Obras y Servicios S.L.",
    description: socialDescription,
    images: [socialImageUrl],
  },
};

function WorksIcon() {
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
    <div className={`${styles.page} ${ibmPlexSans.className}`}>
      <main className={styles.main}>
        <section className={styles.hero} aria-labelledby="hero-title">
          <div className={styles.heroCopy}>
            <p className={styles.eyebrow}>AUREA Obras y Servicios S.L.</p>
            <h1 id="hero-title">Estamos construyendo algo sólido.</h1>
            <p className={styles.intro}>
              Obras y reformas, jardinería y alquiler de herramientas en una nueva web pensada para facilitar tus consultas y próximos proyectos.
            </p>
            <div className={styles.heroActions}>
              <Link className={styles.primaryAction} href="/servicios/jardineria">
                Ver servicios de jardinería
              </Link>
              <span className={styles.status}>Web en desarrollo</span>
            </div>
          </div>

          <div className={styles.buildingScene} aria-hidden="true">
            <div className={styles.sceneLabel}>En construcción</div>
            <div className={styles.scaffold}>
              <span className={styles.scaffoldTop} /><span className={styles.scaffoldLeft} />
              <span className={styles.scaffoldRight} /><span className={styles.scaffoldMiddle} />
              <span className={styles.scaffoldBase} /><span className={`${styles.block} ${styles.blockOne}`} />
              <span className={`${styles.block} ${styles.blockTwo}`} /><span className={`${styles.block} ${styles.blockThree}`} />
              <span className={`${styles.block} ${styles.blockFour}`} />
            </div>
          </div>
        </section>

        <section className={styles.services} aria-labelledby="services-title">
          <div className={styles.sectionHeading}>
            <p className={styles.eyebrow}>Áreas de servicio</p>
            <h2 id="services-title">Soluciones prácticas para poner manos a la obra.</h2>
          </div>
          <div className={styles.serviceGrid}>
            <article className={styles.serviceCard}>
              <div className={styles.icon}><WorksIcon /></div><h3>Obras y servicios</h3>
              <p>Estamos preparando la información de esta área de trabajo.</p>
            </article>
            <article className={`${styles.serviceCard} ${styles.gardenCard}`}>
              <div className={styles.icon}><GardenIcon /></div><h3>Jardinería</h3>
              <p>Una línea especialmente relevante de AUREA para el cuidado de espacios exteriores.</p>
              <Link className={styles.cardLink} href="/servicios/jardineria">
                Ver servicios de jardinería <span aria-hidden="true">→</span>
              </Link>
            </article>
            <article className={`${styles.serviceCard} ${styles.toolsCard}`}>
              <div className={styles.icon}><ToolsIcon /></div><h3>Alquiler de herramientas</h3>
              <p>Consulta el catálogo de herramientas disponible para alquilar.</p>
              <Link className={styles.cardLink} href="/alquiler">Ver catálogo <span aria-hidden="true">→</span></Link>
            </article>
          </div>
          <Link className={styles.servicesAction} href="/servicios">Ver todos los servicios</Link>
        </section>

        <section className={styles.positioning} aria-labelledby="positioning-title">
          <div>
            <p className={styles.eyebrow}>Una forma de trabajar</p>
            <h2 id="positioning-title">Cercanía, claridad y soluciones útiles.</h2>
          </div>
          <p>AUREA reúne obra, jardinería y alquiler para ofrecer un servicio práctico. La web irá incorporando nuevas formas de consultar y organizar cada necesidad.</p>
        </section>

        <section className={styles.development} aria-labelledby="development-title">
          <div className={styles.developmentMark} aria-hidden="true" />
          <div>
            <p className={styles.eyebrow}>Seguimos construyendo</p>
            <h2 id="development-title">Estamos preparando nuevas secciones y el sistema completo de reservas.</h2>
            <p>Algunas funcionalidades aún se están incorporando. Mientras tanto, ya puedes consultar el catálogo de herramientas.</p>
          </div>
          <Link className={styles.secondaryAction} href="/alquiler">Ir al catálogo</Link>
        </section>
      </main>
    </div>
  );
}
