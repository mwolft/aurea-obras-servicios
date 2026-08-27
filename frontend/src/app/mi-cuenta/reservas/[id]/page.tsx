import type { Metadata } from "next";

import { ReservationDetailContent } from "./reservation-detail-content";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "Detalle de reserva | AUREA Obras y Servicios S.L.",
  description: "Consulta privada de una reserva de AUREA Obras y Servicios S.L.",
  robots: { index: false, follow: false },
};

export default function ReservationDetailPage() {
  return (
    <main className={styles.main}>
      <ReservationDetailContent />
    </main>
  );
}
