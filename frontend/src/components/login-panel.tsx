"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "./auth-provider";
import styles from "./login-panel.module.css";

type Mode = "login" | "register";

export function LoginPanel() {
  const { isLoading, login, register, user } = useAuth();
  const [mode, setMode] = useState<Mode>("login");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isStartingGoogle, setIsStartingGoogle] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const errorRef = useRef<HTMLParagraphElement>(null);
  const router = useRouter();
  const googleLoginUrl = process.env.NEXT_PUBLIC_API_URL
    ? `${process.env.NEXT_PUBLIC_API_URL}/api/auth/google`
    : null;

  useEffect(() => {
    errorRef.current?.focus();
  }, [error]);

  const submitLogin = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    const formData = new FormData(event.currentTarget);
    const result = await login({
      email: String(formData.get("email") ?? ""),
      password: String(formData.get("password") ?? ""),
    });
    setIsSubmitting(false);

    if (result.status === "success") {
      router.push("/alquiler");
      return;
    }

    setError(result.message ?? "No se ha podido iniciar sesión. Inténtalo de nuevo.");
  };

  const submitRegistration = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    const formData = new FormData(event.currentTarget);
    const result = await register({
      name: String(formData.get("name") ?? ""),
      email: String(formData.get("email") ?? ""),
      password: String(formData.get("password") ?? ""),
    });
    setIsSubmitting(false);

    if (result.status === "success") {
      router.push("/alquiler");
      return;
    }

    setError(result.message ?? "No se ha podido crear la cuenta. Inténtalo de nuevo.");
  };

  const startGoogleLogin = () => {
    if (!googleLoginUrl) {
      setError("El acceso con Google no está disponible ahora mismo.");
      return;
    }

    setIsStartingGoogle(true);
    window.location.assign(googleLoginUrl);
  };

  if (isLoading) {
    return <p className={styles.status}>Comprobando la sesión…</p>;
  }

  if (user) {
    return (
      <div className={styles.status}>
        <p>Ya has iniciado sesión como {user.name}.</p>
        <button onClick={() => router.push("/mi-cuenta")} type="button">
          Ir a mi cuenta
        </button>
      </div>
    );
  }

  return (
    <div className={styles.panel}>
      <div aria-label="Acceso o registro" className={styles.tabs} role="tablist">
        <button
          aria-selected={mode === "login"}
          className={mode === "login" ? styles.activeTab : undefined}
          onClick={() => {
            setMode("login");
            setError(null);
          }}
          role="tab"
          type="button"
        >
          Iniciar sesión
        </button>
        <button
          aria-selected={mode === "register"}
          className={mode === "register" ? styles.activeTab : undefined}
          onClick={() => {
            setMode("register");
            setError(null);
          }}
          role="tab"
          type="button"
        >
          Crear cuenta
        </button>
      </div>

      {error ? (
        <p className={styles.error} ref={errorRef} tabIndex={-1} role="alert">
          {error}
        </p>
      ) : null}

      <button
        className={styles.googleButton}
        disabled={isSubmitting || isStartingGoogle}
        onClick={startGoogleLogin}
        type="button"
      >
        <span aria-hidden="true" className={styles.googleMark}>G</span>
        {isStartingGoogle ? "Redirigiendo a Google…" : "Continuar con Google"}
      </button>

      <p className={styles.divider}>o continúa con tu correo electrónico</p>

      {mode === "login" ? (
        <form className={styles.form} onSubmit={submitLogin}>
          <label>
            Correo electrónico
            <input autoComplete="email" name="email" required type="email" />
          </label>
          <label>
            Contraseña
            <input autoComplete="current-password" minLength={8} name="password" required type="password" />
          </label>
          <button disabled={isSubmitting} type="submit">
            {isSubmitting ? "Iniciando sesión…" : "Iniciar sesión"}
          </button>
        </form>
      ) : (
        <form className={styles.form} onSubmit={submitRegistration}>
          <label>
            Nombre
            <input autoComplete="name" name="name" required type="text" />
          </label>
          <label>
            Correo electrónico
            <input autoComplete="email" name="email" required type="email" />
          </label>
          <label>
            Contraseña
            <input autoComplete="new-password" minLength={8} name="password" required type="password" />
          </label>
          <button disabled={isSubmitting} type="submit">
            {isSubmitting ? "Creando cuenta…" : "Crear cuenta"}
          </button>
        </form>
      )}
    </div>
  );
}
