import type { Metadata } from "next";

import { legalInfo } from "@/lib/legal";

import { AccountContent } from "./account-content";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: `Mi cuenta | ${legalInfo.companyName}`,
  description: `Área de cliente de ${legalInfo.companyName}.`,
  robots: { index: false, follow: false },
};

export default function AccountPage() {
  return (
    <main className={styles.main}>
      <AccountContent />
    </main>
  );
}
