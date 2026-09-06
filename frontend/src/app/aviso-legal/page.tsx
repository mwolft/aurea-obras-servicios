import type { Metadata } from "next";
import Link from "next/link";

import styles from "../legal-page.module.css";
import { legalInfo } from "@/lib/legal";

export const metadata: Metadata = {
  title: "Aviso legal | AUREA Obras y Servicios",
  description: "Información legal y condiciones de uso de la web de AUREA Obras y Servicios.",
  alternates: { canonical: "/aviso-legal" },
};

export default function LegalNoticePage() {
  return (
    <main className={styles.page}>
      <header className={styles.hero}>
        <p className={styles.eyebrow}>Información legal</p>
        <h1>Aviso legal</h1>
        <p>Estas condiciones regulan el acceso y uso de la web de AUREA Obras y Servicios.</p>
      </header>

      <div className={styles.content}>
        <section aria-labelledby="legal-owner">
          <h2 id="legal-owner">Titular del sitio</h2>
          <article className={styles.legalCard}>
            <dl>
              <div><dt>Razón social</dt><dd>{legalInfo.companyName}</dd></div>
              <div><dt>CIF</dt><dd>{legalInfo.taxId}</dd></div>
              <div><dt>Domicilio</dt><dd>{legalInfo.address}</dd></div>
              <div><dt>Email</dt><dd><a href={`mailto:${legalInfo.legalEmail}`}>{legalInfo.legalEmail}</a></dd></div>
              <div><dt>Teléfono</dt><dd><a href={`tel:${legalInfo.phone.replaceAll(" ", "")}`}>{legalInfo.phone}</a></dd></div>
            </dl>
          </article>
        </section>

        <section aria-labelledby="legal-purpose">
          <h2 id="legal-purpose">Objeto del sitio</h2>
          <p>La web presenta la actividad de AUREA, sus áreas de servicio y el catálogo de herramientas disponibles para alquiler. También permite enviar consultas, crear una cuenta y solicitar reservas cuando la funcionalidad está disponible.</p>
        </section>

        <section aria-labelledby="legal-use">
          <h2 id="legal-use">Condiciones generales de uso</h2>
          <p>La persona usuaria se compromete a utilizar el sitio de forma lícita, diligente y respetuosa con estos contenidos, con la normativa aplicable y con los derechos de terceros.</p>
          <p>No está permitido utilizar el sitio para introducir información falsa, interferir en su funcionamiento o realizar acciones que puedan perjudicar a AUREA, a otras personas usuarias o a terceros.</p>
        </section>

        <section aria-labelledby="legal-intellectual-property">
          <h2 id="legal-intellectual-property">Propiedad intelectual e industrial</h2>
          <p>Los contenidos, elementos gráficos, marcas, diseño y código presentes en esta web están protegidos por la normativa aplicable. Su reproducción, distribución o transformación requiere autorización cuando resulte necesaria.</p>
        </section>

        <section aria-labelledby="legal-responsibility">
          <h2 id="legal-responsibility">Responsabilidad</h2>
          <p>AUREA procura que la información publicada sea clara y actualizada, pero puede modificar contenidos, servicios o funcionalidades cuando sea necesario. La disponibilidad del sitio puede verse afectada temporalmente por tareas técnicas, mantenimiento o circunstancias ajenas al control de AUREA.</p>
        </section>

        <section aria-labelledby="legal-links">
          <h2 id="legal-links">Enlaces externos</h2>
          <p>Cuando esta web incluya enlaces a sitios de terceros, dichos sitios operan bajo sus propias condiciones y políticas. AUREA no controla sus contenidos ni su disponibilidad.</p>
        </section>

        <section aria-labelledby="legal-law">
          <h2 id="legal-law">Marco aplicable</h2>
          <p>Este sitio se rige por la normativa aplicable en España. Cualquier cuestión relacionada con su uso se tratará conforme al marco legal que resulte aplicable en cada caso.</p>
          <p>Consulta también la <Link href="/politica-de-privacidad">Política de privacidad</Link> y la <Link href="/politica-de-cookies">Política de cookies</Link>.</p>
        </section>
      </div>
    </main>
  );
}
