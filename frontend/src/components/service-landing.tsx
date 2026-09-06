import Link from "next/link";

import styles from "./service-landing.module.css";

type WorkApproach = {
  title: string;
  description: string;
};

type ServiceLandingProps = {
  className: string;
  eyebrow: string;
  title: string;
  introduction: string;
  focusTitle: string;
  focusText: string;
  approachTitle: string;
  approachText: string;
  approach: WorkApproach[];
  finalTitle: string;
  finalText: string;
  contactLabel: string;
  visualLabel: string;
  visualType: "fontaneria" | "electricidad" | "obras";
};

function ServiceVisual({ label, type }: { label: string; type: ServiceLandingProps["visualType"] }) {
  return (
    <div aria-hidden="true" className={`${styles.heroVisual} ${styles[type]}`}>
      <span className={styles.visualCircle} />
      <span className={styles.visualLine} />
      <span className={styles.visualShape} />
      <span className={styles.visualLabel}>{label}</span>
    </div>
  );
}

export function ServiceLanding({
  className,
  eyebrow,
  title,
  introduction,
  focusTitle,
  focusText,
  approachTitle,
  approachText,
  approach,
  finalTitle,
  finalText,
  contactLabel,
  visualLabel,
  visualType,
}: Readonly<ServiceLandingProps>) {
  return (
    <div className={className}>
      <main className={styles.main}>
        <section aria-labelledby="service-title" className={styles.hero}>
          <div className={styles.heroCopy}>
            <p className={styles.eyebrow}>{eyebrow}</p>
            <h1 id="service-title">{title}</h1>
            <p className={styles.introduction}>{introduction}</p>
            <div className={styles.heroActions}>
              <Link className={styles.primaryAction} href="/contacto">
                {contactLabel}
              </Link>
              <Link className={styles.secondaryAction} href="/servicios">
                Volver a Servicios
              </Link>
            </div>
          </div>
          <ServiceVisual label={visualLabel} type={visualType} />
        </section>

        <section aria-labelledby="focus-title" className={styles.focus}>
          <div>
            <p className={styles.eyebrow}>Enfoque de AUREA</p>
            <h2 id="focus-title">{focusTitle}</h2>
          </div>
          <p>{focusText}</p>
        </section>

        <section aria-labelledby="approach-title" className={styles.approach}>
          <div className={styles.sectionHeading}>
            <p className={styles.eyebrow}>Cómo se aborda cada consulta</p>
            <h2 id="approach-title">{approachTitle}</h2>
            <p>{approachText}</p>
          </div>
          <div className={styles.approachGrid}>
            {approach.map((item, index) => (
              <article className={styles.approachCard} key={item.title}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <h3>{item.title}</h3>
                <p>{item.description}</p>
              </article>
            ))}
          </div>
        </section>

        <section aria-labelledby="working-title" className={styles.working}>
          <p className={styles.eyebrow}>Forma de trabajar</p>
          <h2 id="working-title">Una intervención pensada para el espacio y la necesidad concreta.</h2>
          <p>
            Cada consulta parte de conocer el caso y ordenar el trabajo de forma clara antes de avanzar.
          </p>
        </section>

        <section aria-labelledby="final-title" className={styles.finalCta}>
          <div>
            <p className={styles.eyebrow}>Contacto</p>
            <h2 id="final-title">{finalTitle}</h2>
            <p>{finalText}</p>
          </div>
          <Link className={styles.finalAction} href="/contacto">
            {contactLabel}
          </Link>
        </section>
      </main>
    </div>
  );
}
