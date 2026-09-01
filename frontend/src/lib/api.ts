import { getStoredToken } from "./auth";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

export async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getStoredToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    if (response.status === 401) {
      if (typeof window !== "undefined" && !endpoint.includes("/auth/login") && !endpoint.includes("/auth/register")) {
        localStorage.removeItem("token");
        window.location.href = "/login";
      }
    }
    const errorData = await response.json().catch(() => ({}));
    let errorMessage = "An API request error occurred.";
    if (typeof errorData.detail === "string") {
      errorMessage = errorData.detail;
    } else if (Array.isArray(errorData.detail)) {
      errorMessage = errorData.detail.map((e: any) => e.msg || e.message || JSON.stringify(e)).join(", ");
    } else if (typeof errorData.detail === "object" && errorData.detail !== null) {
      errorMessage = errorData.detail.message || errorData.detail.msg || JSON.stringify(errorData.detail);
    } else if (errorData.message) {
      errorMessage = errorData.message;
    }
    throw new Error(errorMessage);
  }

  return response.json();
}
