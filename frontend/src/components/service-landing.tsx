import Link from "next/link";

import styles from "./service-landing.module.css";

type WorkApproach = {
  title: string;
  description: string;
};

type BreadcrumbItem = {
  label: string;
  href?: string;
};

type ContextualBlock = {
  eyebrow: string;
  title: string;
  text: string;
  items?: WorkApproach[];
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
  finalContactLabel?: string;
  visualLabel: string;
  visualType: "fontaneria" | "electricidad" | "obras";
  breadcrumb?: BreadcrumbItem[];
  contextualBlock?: ContextualBlock;
  sectionLabels?: {
    focusEyebrow?: string;
    approachEyebrow?: string;
  };
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
  finalContactLabel,
  visualLabel,
  visualType,
  breadcrumb,
  contextualBlock,
  sectionLabels,
}: Readonly<ServiceLandingProps>) {
  return (
    <div className={className}>
      <main className={styles.main}>
        {breadcrumb ? (
          <nav aria-label="Migas de pan" className={styles.breadcrumbs}>
            <ol>
              {breadcrumb.map((item, index) => {
                const isCurrentPage = index === breadcrumb.length - 1;

                return (
                  <li aria-current={isCurrentPage ? "page" : undefined} key={item.label}>
                    {item.href && !isCurrentPage ? <Link href={item.href}>{item.label}</Link> : item.label}
                  </li>
                );
              })}
            </ol>
          </nav>
        ) : null}

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
            <p className={styles.eyebrow}>{sectionLabels?.focusEyebrow ?? "Enfoque de AUREA"}</p>
            <h2 id="focus-title">{focusTitle}</h2>
          </div>
          <p>{focusText}</p>
        </section>

        {contextualBlock ? (
          <section
            aria-labelledby="contextual-title"
            className={`${styles.contextual}${contextualBlock.items ? ` ${styles.contextualWithItems}` : ""}`}
          >
            <div>
              <p className={styles.eyebrow}>{contextualBlock.eyebrow}</p>
              <h2 id="contextual-title">{contextualBlock.title}</h2>
            </div>
            <p>{contextualBlock.text}</p>
            {contextualBlock.items ? (
              <div className={styles.contextualGrid}>
                {contextualBlock.items.map((item) => (
                  <article className={styles.approachCard} key={item.title}>
                    <h3>{item.title}</h3>
                    <p>{item.description}</p>
                  </article>
                ))}
              </div>
            ) : null}
          </section>
        ) : null}

        <section aria-labelledby="approach-title" className={styles.approach}>
          <div className={styles.sectionHeading}>
            <p className={styles.eyebrow}>{sectionLabels?.approachEyebrow ?? "Cómo se aborda cada consulta"}</p>
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
            {finalContactLabel ?? contactLabel}
          </Link>
        </section>
      </main>
    </div>
  );
}
