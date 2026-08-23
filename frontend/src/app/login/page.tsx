import type { Metadata } from "next";

import { LoginPanel } from "@/components/login-panel";

import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "Iniciar sesión | AUREA Obras y Servicios S.L.",
  description: "Accede o crea una cuenta para gestionar tus solicitudes de alquiler en AUREA.",
};

export default function LoginPage() {
  return (
    <main className={styles.main}>
      <div className={styles.layout}>
        <section className={styles.introduction} aria-labelledby="login-title">
          <p className={styles.eyebrow}>Área de clientes</p>
          <h1 id="login-title">Accede a tu cuenta.</h1>
          <p>
            Mantén tus solicitudes y reservas vinculadas a tus datos mientras seguimos completando
            el área de cliente de AUREA.
          </p>
          <ul className={styles.benefits}>
            <li>Una relación más clara con tus solicitudes.</li>
            <li>Acceso a tu área de cliente desde cualquier momento.</li>
            <li>Nuevas funcionalidades que iremos incorporando poco a poco.</li>
          </ul>
        </section>
        <section className={styles.card} aria-label="Acceso o creación de cuenta">
          <LoginPanel />
        </section>
      </div>
    </main>
  );
}
