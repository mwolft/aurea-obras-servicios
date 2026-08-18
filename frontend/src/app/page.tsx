"use client";

import { useEffect, useState } from "react";

import { getApiHealth, type ApiHealthStatus } from "@/lib/api";

export default function Home() {
  const [backendStatus, setBackendStatus] = useState<ApiHealthStatus>("unavailable");

  useEffect(() => {
    getApiHealth().then(setBackendStatus);
  }, []);

  return (
    <main>
      <h1>AUREA Obras y Servicios</h1>
      <p>Frontend: OK</p>
      <p>Backend API: {backendStatus === "ok" ? "OK" : "unavailable"}</p>
    </main>
  );
}
