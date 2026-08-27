import type { Metadata } from "next";

import { AccountContent } from "./account-content";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "Mi cuenta | AUREA Obras y Servicios S.L.",
  description: "Área de cliente de AUREA Obras y Servicios S.L.",
  robots: { index: false, follow: false },
};

export default function AccountPage() {
  return (
    <main className={styles.main}>
      <AccountContent />
    </main>
  );
}
