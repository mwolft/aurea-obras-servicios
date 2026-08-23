"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/auth-provider";
import { getAccountReservations, type AccountReservation } from "@/lib/api";

import styles from "./page.module.css";

type ReservationsState = { kind: "loading" } | { kind: "success"; reservations: AccountReservation[] } | { kind: "error" };

const statusLabels: Record<AccountReservation["status"], string> = { pending_review: "Pendiente de revisión", pending_payment: "Pendiente de pago", confirmed: "Confirmada", cancelled: "Cancelada", expired: "Caducada" };

function formatDate(value: string) { return new Intl.DateTimeFormat("es-ES", { dateStyle: "medium" }).format(new Date(`${value}T00:00:00`)); }
function formatAmount(value: string | null) { return value === null ? null : new Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR" }).format(Number(value)); }

function ReservationCard({ reservation }: { reservation: AccountReservation }) {
  const expiredPayment = reservation.status === "pending_payment" && reservation.payment_expired;
  const total = formatAmount(reservation.total_amount);
  const statusClass = expiredPayment ? styles.statusExpired : styles[`status${reservation.status}`];

  return <article className={styles.reservationCard}>
    <div className={styles.reservationHeader}><div><p className={styles.toolLabel}>Herramienta</p><h3>{reservation.tool.name}</h3></div><span className={`${styles.reservationStatus} ${statusClass}`}>{expiredPayment ? "Caducada" : statusLabels[reservation.status]}</span></div>
    <dl className={styles.reservationDetails}>
      <div><dt>Fechas</dt><dd>{formatDate(reservation.start_date)} – {formatDate(reservation.end_date)}</dd></div>
      {reservation.charged_days !== null && <div><dt>Duración</dt><dd>{reservation.charged_days} {reservation.charged_days === 1 ? "día" : "días"}</dd></div>}
      <div><dt>Modalidad</dt><dd>{reservation.fulfillment_method === "delivery" ? "Transporte" : "Recogida en almacén"}</dd></div>
      {reservation.fulfillment_method === "delivery" && reservation.delivery_address && <div><dt>Dirección</dt><dd>{reservation.delivery_address}</dd></div>}
    </dl>
    {reservation.status === "pending_review" ? <p className={styles.reservationNotice}>El transporte está pendiente de valoración. Te mostraremos el importe definitivo después de la revisión.</p> : total ? <div className={styles.total}><span>Total</span><strong>{total}</strong></div> : null}
    {reservation.status === "pending_payment" && !expiredPayment && reservation.payment_expires_at && <p className={styles.paymentNotice}>Pendiente de pago hasta el {new Intl.DateTimeFormat("es-ES", { dateStyle: "medium", timeStyle: "short" }).format(new Date(reservation.payment_expires_at))}.</p>}
    <Link className={styles.reservationLink} href={`/mi-cuenta/reservas/${reservation.id}`}>Ver reserva<span aria-hidden="true"> →</span></Link>
  </article>;
}

export function AccountContent() {
  const { isLoading, refreshUser, user } = useAuth();
  const router = useRouter();
  const [reservationsState, setReservationsState] = useState<ReservationsState>({ kind: "loading" });

  useEffect(() => { if (!isLoading && !user) router.replace("/login"); }, [isLoading, router, user]);
  useEffect(() => {
    if (!user) return;
    let mounted = true;
    void getAccountReservations().then(async (result) => {
      if (!mounted) return;
      if (result.status === "unauthenticated") { await refreshUser(); return; }
      setReservationsState(result.status === "success" ? { kind: "success", reservations: result.reservations } : { kind: "error" });
    });
    return () => { mounted = false; };
  }, [refreshUser, user]);

  if (isLoading || !user) return <section aria-live="polite" className={styles.status}><p>Comprobando la sesión…</p></section>;

  return <section className={styles.account} aria-labelledby="account-title">
    <header className={styles.heading}><p className={styles.eyebrow}>Área de cliente</p><h1 id="account-title">Mi cuenta</h1><p>Desde aquí podrás consultar tu relación con AUREA a medida que habilitemos nuevas funciones.</p></header>
    <section className={styles.card} aria-labelledby="profile-title"><div className={styles.cardHeader}><h2 id="profile-title">Tus datos</h2><span className={styles.sessionStatus}>Sesión activa</span></div><dl className={styles.details}><div><dt>Nombre</dt><dd>{user.name}</dd></div><div><dt>Correo electrónico</dt><dd>{user.email}</dd></div></dl></section>
    <section className={styles.reservations} aria-labelledby="reservations-title"><div className={styles.reservationsHeading}><div><p className={styles.eyebrow}>Tus solicitudes</p><h2 id="reservations-title">Mis reservas</h2></div></div>
      {reservationsState.kind === "loading" && <p aria-live="polite" className={styles.reservationsFeedback}>Cargando tus reservas…</p>}
      {reservationsState.kind === "error" && <p className={styles.reservationsFeedback} role="alert">No podemos cargar tus reservas ahora mismo. Inténtalo de nuevo más tarde.</p>}
      {reservationsState.kind === "success" && reservationsState.reservations.length === 0 && <p className={styles.reservationsFeedback}>Todavía no tienes reservas asociadas a esta cuenta.</p>}
      {reservationsState.kind === "success" && reservationsState.reservations.length > 0 && <div className={styles.reservationList}>{reservationsState.reservations.map((reservation) => <ReservationCard key={reservation.id} reservation={reservation} />)}</div>}
    </section>
  </section>;
}
