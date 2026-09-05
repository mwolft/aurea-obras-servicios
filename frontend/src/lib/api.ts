export type ApiHealthStatus = "ok" | "unavailable";

export type ContactMessageRequest = {
  name: string;
  email: string;
  phone: string;
  subject: string;
  message: string;
  privacyAccepted: boolean;
  website: string;
};

export type SendContactMessageResult =
  | { status: "success" }
  | { status: "validation_error" }
  | { status: "error" };

export type CatalogImage = {
  url: string;
  position: number;
};

export type CatalogTool = {
  id: number;
  name: string;
  category: string;
  description: string | null;
  daily_price: string;
  deposit_amount: string;
  pickup_available: boolean;
  delivery_available: boolean;
  delivery_price_per_km: string | null;
  is_available: boolean;
  included_km: number | null;
  extra_km_price: string | null;
  images: CatalogImage[];
};

export type CatalogResult =
  | { status: "success"; tools: CatalogTool[] }
  | { status: "error" };

export type CatalogToolResult =
  | { status: "success"; tool: CatalogTool }
  | { status: "not_found" }
  | { status: "error" };

export type ToolAvailability = {
  tool_id: number;
  start_date: string;
  end_date: string;
  available: boolean;
};

export type ToolAvailabilityResult =
  | { status: "success"; availability: ToolAvailability }
  | { status: "not_found" }
  | { status: "error"; message?: string };

export type ReservationRequest = {
  start_date: string;
  end_date: string;
  customer_name: string;
  customer_email: string;
  customer_phone: string;
  fulfillment_method: "pickup" | "delivery";
  delivery_address?: string;
  terms_accepted: boolean;
  privacy_accepted: boolean;
};

export type ReservationResponse = {
  id: number;
  tool_id: number;
  start_date: string;
  end_date: string;
  status: "pending_review" | "pending_payment" | "confirmed" | "cancelled" | "expired";
  fulfillment_method: "pickup" | "delivery";
  payment_expires_at: string | null;
  charged_days: number | null;
  daily_price_snapshot: string | null;
  delivery_price_per_km_snapshot: string | null;
  rental_amount: string | null;
  delivery_amount: string | null;
  total_amount: string | null;
  deposit_amount: string;
};

export type CreateReservationResult =
  | { status: "success"; reservation: ReservationResponse }
  | { status: "validation_error"; message: string }
  | { status: "not_found" }
  | { status: "conflict"; message: string }
  | { status: "error"; message?: string };

export type AuthUser = {
  id: number;
  name: string;
  email: string;
};

export type AuthCredentials = {
  email: string;
  password: string;
};

export type RegistrationCredentials = AuthCredentials & {
  name: string;
};

export type AuthResult =
  | { status: "success"; user: AuthUser }
  | { status: "validation_error"; message: string }
  | { status: "conflict"; message: string }
  | { status: "unauthorized"; message: string }
  | { status: "error"; message?: string };

export type CurrentUserResult =
  | { status: "success"; user: AuthUser }
  | { status: "unauthenticated" }
  | { status: "error" };

export type AccountReservation = {
  id: number;
  tool: { id: number; name: string };
  start_date: string;
  end_date: string;
  status: "pending_review" | "pending_payment" | "confirmed" | "cancelled" | "expired";
  payment_expired: boolean;
  fulfillment_method: "pickup" | "delivery" | null;
  delivery_address: string | null;
  charged_days: number | null;
  rental_amount: string | null;
  delivery_amount: string | null;
  total_amount: string | null;
  payment_expires_at: string | null;
  created_at: string;
};

export type AccountReservationsResult =
  | { status: "success"; reservations: AccountReservation[] }
  | { status: "unauthenticated" }
  | { status: "error" };

export type AccountReservationDetail = AccountReservation & {
  billable_km: string | null;
  daily_price_snapshot: string | null;
  delivery_price_per_km_snapshot: string | null;
  customer_name: string | null;
  customer_email: string | null;
  customer_phone: string | null;
};

export type AccountReservationDetailResult =
  | { status: "success"; reservation: AccountReservationDetail }
  | { status: "unauthenticated" }
  | { status: "not_found" }
  | { status: "error" };

export async function getApiHealth(): Promise<ApiHealthStatus> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;

  if (!apiUrl) {
    return "unavailable";
  }

  try {
    const response = await fetch(`${apiUrl}/api/health`);
    const data: unknown = await response.json();

    if (response.ok && data && typeof data === "object" && "status" in data && data.status === "ok") {
      return "ok";
    }
  } catch {
    // The API is optional for this initial status check.
  }

  return "unavailable";
}

export async function sendContactMessage(
  message: ContactMessageRequest,
): Promise<SendContactMessageResult> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;

  if (!apiUrl) {
    return { status: "error" };
  }

  try {
    const response = await fetch(`${apiUrl}/api/contact`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(message),
    });
    const data: unknown = await response.json().catch(() => null);

    if (
      response.ok &&
      data &&
      typeof data === "object" &&
      "success" in data &&
      data.success === true
    ) {
      return { status: "success" };
    }

    if (response.status === 400) {
      return { status: "validation_error" };
    }
  } catch {
    // Contact requests may fail when the API cannot be reached.
  }

  return { status: "error" };
}

export async function getCatalogTools(): Promise<CatalogResult> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;

  if (!apiUrl) {
    return { status: "error" };
  }

  try {
    const response = await fetch(`${apiUrl}/api/tools`, { cache: "no-store" });
    const data: unknown = await response.json();

    if (response.ok && Array.isArray(data)) {
      return { status: "success", tools: data as CatalogTool[] };
    }
  } catch {
    // The catalogue is unavailable when the API cannot be reached.
  }

  return { status: "error" };
}

export async function getCatalogTool(id: number): Promise<CatalogToolResult> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;

  if (!apiUrl) {
    return { status: "error" };
  }

  try {
    const response = await fetch(`${apiUrl}/api/tools/${id}`, { cache: "no-store" });

    if (response.status === 404) {
      return { status: "not_found" };
    }

    const data: unknown = await response.json();

    if (response.ok && data && typeof data === "object" && !Array.isArray(data)) {
      return { status: "success", tool: data as CatalogTool };
    }
  } catch {
    // The catalogue is unavailable when the API cannot be reached.
  }

  return { status: "error" };
}

export async function getToolAvailability(
  id: number,
  startDate: string,
  endDate: string,
): Promise<ToolAvailabilityResult> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;

  if (!apiUrl) {
    return { status: "error" };
  }

  try {
    const searchParams = new URLSearchParams({
      start_date: startDate,
      end_date: endDate,
    });
    const response = await fetch(`${apiUrl}/api/tools/${id}/availability?${searchParams}`, {
      cache: "no-store",
    });

    if (response.status === 404) {
      return { status: "not_found" };
    }

    const data: unknown = await response.json();

    if (response.ok && data && typeof data === "object" && !Array.isArray(data)) {
      return { status: "success", availability: data as ToolAvailability };
    }

    if (data && typeof data === "object" && "error" in data && typeof data.error === "string") {
      return { status: "error", message: data.error };
    }
  } catch {
    // Availability cannot be confirmed when the API cannot be reached.
  }

  return { status: "error" };
}

export async function createToolReservation(
  id: number,
  reservation: ReservationRequest,
): Promise<CreateReservationResult> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;

  if (!apiUrl) {
    return { status: "error" };
  }

  try {
    const response = await fetch(`${apiUrl}/api/tools/${id}/reservations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(reservation),
    });
    const data: unknown = await response.json();
    const message =
      data && typeof data === "object" && "error" in data && typeof data.error === "string"
        ? data.error
        : undefined;

    if (response.status === 400) {
      return { status: "validation_error", message: message ?? "Revisa los datos de la solicitud." };
    }

    if (response.status === 404) {
      return { status: "not_found" };
    }

    if (response.status === 409) {
      return {
        status: "conflict",
        message: message ?? "La herramienta ya no está disponible para esas fechas.",
      };
    }

    if (response.ok && data && typeof data === "object" && !Array.isArray(data)) {
      return { status: "success", reservation: data as ReservationResponse };
    }
  } catch {
    // Reservation requests may fail when the API cannot be reached.
  }

  return { status: "error" };
}

function getApiErrorMessage(data: unknown): string | undefined {
  if (data && typeof data === "object" && "error" in data && typeof data.error === "string") {
    return data.error;
  }

  return undefined;
}

async function sendAuthRequest(
  path: "register" | "login",
  credentials: RegistrationCredentials | AuthCredentials,
): Promise<AuthResult> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;

  if (!apiUrl) {
    return { status: "error" };
  }

  try {
    const response = await fetch(`${apiUrl}/api/auth/${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(credentials),
    });
    const data: unknown = await response.json();
    const message = getApiErrorMessage(data);

    if (response.ok && data && typeof data === "object" && !Array.isArray(data)) {
      return { status: "success", user: data as AuthUser };
    }

    if (response.status === 400) {
      return { status: "validation_error", message: message ?? "Revisa los datos introducidos." };
    }

    if (response.status === 409) {
      return { status: "conflict", message: message ?? "Ya existe una cuenta con ese correo." };
    }

    if (response.status === 401) {
      return { status: "unauthorized", message: message ?? "Credenciales incorrectas." };
    }
  } catch {
    // Authentication is unavailable when the API cannot be reached.
  }

  return { status: "error" };
}

export function registerUser(credentials: RegistrationCredentials): Promise<AuthResult> {
  return sendAuthRequest("register", credentials);
}

export function loginUser(credentials: AuthCredentials): Promise<AuthResult> {
  return sendAuthRequest("login", credentials);
}

export async function getCurrentUser(): Promise<CurrentUserResult> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;

  if (!apiUrl) {
    return { status: "error" };
  }

  try {
    const response = await fetch(`${apiUrl}/api/auth/me`, {
      cache: "no-store",
      credentials: "include",
    });

    if (response.status === 401) {
      return { status: "unauthenticated" };
    }

    const data: unknown = await response.json();
    if (response.ok && data && typeof data === "object" && !Array.isArray(data)) {
      return { status: "success", user: data as AuthUser };
    }
  } catch {
    // A missing session must not break public pages.
  }

  return { status: "error" };
}

export async function getAccountReservations(): Promise<AccountReservationsResult> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;

  if (!apiUrl) {
    return { status: "error" };
  }

  try {
    const response = await fetch(`${apiUrl}/api/account/reservations`, {
      cache: "no-store",
      credentials: "include",
    });

    if (response.status === 401) {
      return { status: "unauthenticated" };
    }

    const data: unknown = await response.json();
    if (response.ok && Array.isArray(data)) {
      return { status: "success", reservations: data as AccountReservation[] };
    }
  } catch {
    // Account reservations are unavailable when the API cannot be reached.
  }

  return { status: "error" };
}

export async function getAccountReservation(
  id: number,
): Promise<AccountReservationDetailResult> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;

  if (!apiUrl) {
    return { status: "error" };
  }

  try {
    const response = await fetch(`${apiUrl}/api/account/reservations/${id}`, {
      cache: "no-store",
      credentials: "include",
    });

    if (response.status === 401) {
      return { status: "unauthenticated" };
    }

    if (response.status === 404) {
      return { status: "not_found" };
    }

    const data: unknown = await response.json();
    if (response.ok && data && typeof data === "object" && !Array.isArray(data)) {
      return { status: "success", reservation: data as AccountReservationDetail };
    }
  } catch {
    // Reservation details are unavailable when the API cannot be reached.
  }

  return { status: "error" };
}

export async function logoutUser(): Promise<{ status: "success" } | { status: "error" }> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;

  if (!apiUrl) {
    return { status: "error" };
  }

  try {
    const response = await fetch(`${apiUrl}/api/auth/logout`, {
      method: "POST",
      credentials: "include",
    });
    if (response.ok) {
      return { status: "success" };
    }
  } catch {
    // A failed logout leaves the client-side session state unchanged.
  }

  return { status: "error" };
}
