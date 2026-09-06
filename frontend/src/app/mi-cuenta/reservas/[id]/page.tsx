import type { Metadata } from "next";

import { legalInfo } from "@/lib/legal";

import { ReservationDetailContent } from "./reservation-detail-content";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: `Detalle de reserva | ${legalInfo.companyName}`,
  description: `Consulta privada de una reserva de ${legalInfo.companyName}.`,
  robots: { index: false, follow: false },
};

export default function ReservationDetailPage() {
  return (
    <main className={styles.main}>
      <ReservationDetailContent />
    </main>
  );
}
