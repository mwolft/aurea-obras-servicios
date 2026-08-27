import type { Metadata } from "next";

import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "Contacto | AUREA Obras y Servicios S.L.",
  description: "Contacta con AUREA Obras y Servicios S.L. para plantear tu necesidad de forma sencilla.",
  alternates: { canonical: "/contacto" },
};

export default function ContactPage() {
  return (
    <main className={styles.page}>
      <section aria-labelledby="contact-title" className={styles.hero}>
        <p className={styles.eyebrow}>Contacto</p>
        <h1 id="contact-title">Cuéntanos qué necesitas.</h1>
        <p>
          Estamos preparando nuestros canales de contacto para poder atender cada consulta con
          claridad y cercanía.
        </p>
      </section>

      <section aria-labelledby="channels-title" className={styles.channels}>
        <div>
          <p className={styles.eyebrow}>Canales de contacto</p>
          <h2 id="channels-title">Próximamente podrás encontrarnos aquí.</h2>
        </div>
        <p>
          Incorporaremos los datos de teléfono, correo electrónico y área de atención cuando estén
          confirmados.
        </p>
      </section>

      <section aria-labelledby="form-title" className={styles.formSection}>
        <div className={styles.formHeading}>
          <p className={styles.eyebrow}>Formulario de contacto</p>
          <h2 id="form-title">Prepara tu consulta.</h2>
          <p>
            Este formulario estará disponible próximamente. Por ahora puedes dejar preparada la
            información que necesitaremos para atenderte.
          </p>
        </div>

        <form aria-describedby="form-status" className={styles.form}>
          <div className={styles.fieldGrid}>
            <label>
              Nombre
              <input autoComplete="name" name="name" type="text" />
            </label>
            <label>
              Email
              <input autoComplete="email" name="email" type="email" />
            </label>
            <label>
              Teléfono
              <input autoComplete="tel" name="phone" type="tel" />
            </label>
            <label>
              Asunto
              <input name="subject" type="text" />
            </label>
          </div>

          <label>
            Mensaje
            <textarea name="message" rows={6} />
          </label>

          <label className={styles.privacy}>
            <input name="privacy" type="checkbox" />
            <span>He leído y acepto la política de privacidad.</span>
          </label>

          <div className={styles.formFooter}>
            <p id="form-status" role="status">
              El envío de consultas todavía no está disponible. No se enviará ningún dato desde
              este formulario.
            </p>
            <button disabled type="submit">Envío próximamente</button>
          </div>
        </form>
      </section>

      <section aria-labelledby="closing-title" className={styles.closing}>
        <p className={styles.eyebrow}>AUREA</p>
        <h2 id="closing-title">Estamos terminando de preparar esta vía de contacto.</h2>
        <p>Incorporaremos la información necesaria para que puedas escribirnos o llamarnos con facilidad.</p>
      </section>

      {/* TODO: incorporar teléfono, email y área de atención confirmados por Emilio. */}
    </main>
  );
}
