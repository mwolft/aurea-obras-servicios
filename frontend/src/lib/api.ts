export type ApiHealthStatus = "ok" | "unavailable";

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
