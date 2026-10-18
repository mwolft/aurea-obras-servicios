import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";

import styles from "./page.module.css";

const serviceAreas = [
  {
    name: "Fontanería",
    description:
      "Una de las áreas de trabajo que forman parte de la oferta multiservicio de AUREA.",
    href: "/servicios/fontaneria",
  },
  {
    name: "Electricidad",
    description:
      "Servicios de electricidad integrados en la propuesta de trabajo de AUREA.",
    href: "/servicios/electricidad",
  },
  {
    name: "Obras / Reformas",
    description:
      "Trabajos de obras y reformas dentro de las áreas de servicio de AUREA.",
    href: "/servicios/obras-reformas",
  },
];

export const metadata: Metadata = {
  title: "Servicios en Ciudad Real | AUREA",
  description:
    "Servicios de jardinería, fontanería, electricidad y obras y reformas en Ciudad Real capital y provincia. Conoce las áreas de trabajo de AUREA.",
  alternates: { canonical: "/servicios" },
};

export default function ServicesPage() {
  return (
    <div className={styles.page}>
      <main className={styles.main}>
        <section aria-labelledby="services-title" className={styles.hero}>
          <div className={styles.heroCopy}>
            <p className={styles.eyebrow}>Servicios</p>
            <h1 id="services-title">Servicios de jardinería, fontanería, electricidad y reformas en Ciudad Real</h1>
            <p className={styles.intro}>
              AUREA reúne distintos servicios para viviendas, terrenos e instalaciones en Ciudad Real capital y provincia. Cuéntanos qué trabajo necesitas y valoraremos la mejor forma de ayudarte.
            </p>
            <div className={styles.heroActions}>
              <Link className={styles.primaryAction} href="/contacto">
                Cuéntanos qué necesitas
              </Link>
              <Link className={styles.secondaryAction} href="/servicios/jardineria">
                Conocer Jardinería
              </Link>
            </div>
          </div>
          <div className={styles.heroVisual}>
            <Image
              alt="Trabajador realizando labores de jardinería"
              className={styles.heroImage}
              fill
              priority
              sizes="(max-width: 700px) calc(100vw - 2rem), (max-width: 920px) calc(100vw - 3rem), 30rem"
              src="/trabajador-de-jardineria.webp"
            />
          </div>
        </section>

        <section aria-labelledby="gardening-title" className={styles.featuredService}>
          <div className={styles.featuredCopy}>
            <p className={styles.eyebrow}>Jardinería</p>
            <h2 id="gardening-title">Jardinería y mantenimiento de espacios exteriores</h2>
            <p>
              Trabajamos en parcelas, jardines y zonas exteriores de Ciudad Real, con actuaciones de desbroce, control de maleza y preparación de terrenos.
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
          <div className={styles.featuredVisual}>
            <Image
              alt="Jardín de urbanización con césped, árboles y zonas verdes"
              className={styles.featuredImage}
              fill
              sizes="(max-width: 700px) calc(100vw - 2rem), (max-width: 850px) calc(100vw - 3rem), 32rem"
              src="/jardin-soleado-con-sombrillas.webp"
            />
          </div>
        </section>

        <section aria-labelledby="service-areas-title" className={styles.serviceAreas}>
          <div className={styles.sectionHeading}>
            <p className={styles.eyebrow}>Áreas de AUREA</p>
            <h2 id="service-areas-title">Una empresa multiservicio.</h2>
            <p>
              Además de Jardinería, AUREA desarrolla Fontanería, Electricidad y Obras / Reformas como áreas de actividad en Ciudad Real capital y provincia.
            </p>
          </div>
          <div className={styles.areasGrid}>
            {serviceAreas.map((service, index) => (
              <article className={styles.serviceCard} key={service.name}>
                <span className={styles.cardNumber}>{String(index + 2).padStart(2, "0")}</span>
                <h3>{service.name}</h3>
                <p>{service.description}</p>
                <Link className={styles.cardLink} href={service.href}>
                  Conocer {service.name}
                </Link>
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
