import type { Metadata } from "next";
import Link from "next/link";

import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "Política de cookies | AUREA Obras y Servicios",
  description: "Información sobre el uso de cookies técnicas en la web de AUREA Obras y Servicios.",
  alternates: { canonical: "/politica-de-cookies" },
};

export default function CookiePolicyPage() {
  return (
    <main className={styles.page}>
      <header className={styles.hero}>
        <p className={styles.eyebrow}>Información legal</p>
        <h1>Política de cookies</h1>
        <p>
          En esta página explicamos de forma clara qué son las cookies y cómo se utilizan actualmente en la web de AUREA.
        </p>
      </header>

      <div className={styles.content}>
        <section aria-labelledby="what-are-cookies">
          <h2 id="what-are-cookies">¿Qué son las cookies?</h2>
          <p>
            Las cookies son pequeños archivos que un sitio web puede almacenar o consultar en el navegador para que determinadas funciones funcionen correctamente. Algunas son necesarias para servicios concretos, como mantener una sesión iniciada.
          </p>
        </section>

        <section aria-labelledby="cookies-in-use">
          <h2 id="cookies-in-use">Cookies que utiliza AUREA</h2>
          <p>
            Actualmente, AUREA utiliza una cookie estrictamente necesaria para el funcionamiento de la autenticación de usuarios y del área de administración. No se utilizan cookies analíticas ni publicitarias.
          </p>

          <article className={styles.cookieCard}>
            <h3>Cookie técnica de sesión</h3>
            <dl>
              <div>
                <dt>Nombre</dt>
                <dd><code>aurea_session</code></dd>
              </div>
              <div>
                <dt>Origen</dt>
                <dd>AUREA, mediante su backend Flask.</dd>
              </div>
              <div>
                <dt>Finalidad</dt>
                <dd>Mantener la sesión de usuario y administrador, y apoyar el flujo de autenticación con Google OAuth cuando se utiliza.</dd>
              </div>
              <div>
                <dt>Tipo</dt>
                <dd>Estrictamente necesaria o técnica.</dd>
              </div>
              <div>
                <dt>Características</dt>
                <dd>Se configura con <code>HttpOnly</code> y <code>SameSite=Lax</code>; utiliza <code>Secure</code> en producción. No se configura un dominio explícito ni una duración permanente explícita.</dd>
              </div>
            </dl>
          </article>
        </section>

        <section aria-labelledby="why-no-banner">
          <h2 id="why-no-banner">Cookies necesarias</h2>
          <p>
            Esta cookie permite que las personas autenticadas mantengan su sesión y accedan a las funciones que requieren identificación. Por su carácter técnico, permanece activa mientras sea necesaria para prestar esas funciones.
          </p>
        </section>

        <section aria-labelledby="google-oauth">
          <h2 id="google-oauth">Inicio de sesión con Google</h2>
          <p>
            Google OAuth solo interviene si eliges iniciar sesión con Google. AUREA no carga cookies adicionales de Google en sus páginas públicas por este motivo. Al acceder al servicio de Google, ese proveedor aplica sus propias condiciones y tecnologías en su dominio.
          </p>
        </section>

        <section aria-labelledby="future-technologies">
          <h2 id="future-technologies">Tecnologías opcionales en el futuro</h2>
          <p>
            Si AUREA incorpora en el futuro tecnologías analíticas, publicitarias u otras cookies opcionales, se habilitará el mecanismo de consentimiento correspondiente antes de activarlas.
          </p>
        </section>

        <aside className={styles.legalNote} aria-label="Información legal adicional">
          <p>
            Consulta también el <Link href="/aviso-legal">Aviso Legal</Link> y la{" "}
            <Link href="/politica-de-privacidad">Política de Privacidad</Link> de AUREA.
          </p>
        </aside>
      </div>
    </main>
  );
}
