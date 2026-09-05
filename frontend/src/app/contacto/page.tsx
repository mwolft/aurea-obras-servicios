import type { Metadata } from "next";

import { ContactForm } from "./contact-form";
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
          Explícanos tu consulta para que podamos conocer mejor el trabajo que necesitas.
        </p>
      </section>

      <section aria-labelledby="form-title" className={styles.formSection}>
        <div className={styles.formHeading}>
          <p className={styles.eyebrow}>Formulario de contacto</p>
          <h2 id="form-title">Estamos listos para conocer tu consulta.</h2>
          <p>
            Indica los datos básicos y cuéntanos qué necesitas. Usaremos esta información únicamente para responder a tu consulta.
          </p>
        </div>

        <ContactForm />
      </section>

      <section aria-labelledby="closing-title" className={styles.closing}>
        <p className={styles.eyebrow}>AUREA</p>
        <h2 id="closing-title">Un punto de partida para tu próximo proyecto.</h2>
        <p>Cuéntanos qué necesitas y comparte los datos que nos ayuden a entender tu consulta.</p>
      </section>
    </main>
  );
}
