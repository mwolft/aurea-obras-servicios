import type { Metadata } from "next";
import { Suspense } from "react";

import { PaymentConfirmation } from "./payment-confirmation";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "Estado de la reserva | AUREA Obras y Servicios",
  description: "Consulta el estado confirmado de tu reserva de alquiler en AUREA.",
  robots: { index: false, follow: false },
};

function PaymentConfirmationFallback() {
  return (
    <section aria-live="polite" className={styles.card}>
      <p className={styles.eyebrow}>AUREA · ALQUILER</p>
      <h1>Estamos comprobando tu pago…</h1>
      <p>Estamos consultando el estado seguro de tu reserva.</p>
    </section>
  );
}

export default function ReservationConfirmationPage() {
  return (
    <main className={styles.main}>
      <Suspense fallback={<PaymentConfirmationFallback />}>
        <PaymentConfirmation />
      </Suspense>
    </main>
  );
}
