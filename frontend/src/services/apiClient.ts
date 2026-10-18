import type { ApiEnvelope, AuthToken, User } from "./types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL;
const TOKEN_KEY = "gyros_token";

export class ApiError extends Error {
  status: number;
  errors: Record<string, string>;

  constructor(
    status: number,
    message: string,
    errors: Record<string, string> = {},
  ) {
    super(message);
    this.status = status;
    this.errors = errors;
  }
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function saveToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  const token = getToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  let envelope: ApiEnvelope<T>;
  try {
    envelope = await response.json();
  } catch {
    throw new ApiError(response.status, "Unexpected server response");
  }

  if (!response.ok) {
    const message =
      envelope.message?.error ??
      Object.values(envelope.error ?? {})[0] ??
      "Request failed";
    throw new ApiError(response.status, message, envelope.error ?? {});
  }

  return envelope.data;
}

export async function requestForm<T>(
  path: string,
  formData: FormData,
): Promise<T> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers,
    body: formData,
  });

  let envelope: ApiEnvelope<T>;
  try {
    envelope = await response.json();
  } catch {
    throw new ApiError(response.status, "Unexpected server response");
  }

  if (!response.ok) {
    const message =
      envelope.message?.error ??
      Object.values(envelope.error ?? {})[0] ??
      "Request failed";
    throw new ApiError(response.status, message, envelope.error ?? {});
  }

  return envelope.data;
}

export async function login(
  email: string,
  password: string,
): Promise<{ token: AuthToken; user: User }> {
  const data = await request<{ token: AuthToken; user: User }>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  saveToken(data.token.access_token);
  return data;
}

export async function register(
  fullName: string,
  email: string,
  password: string,
): Promise<{ user: User }> {
  return request<{ user: User }>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ full_name: fullName, email, password }),
  });
}

export async function getMe(): Promise<{ user: User }> {
  return request<{ user: User }>("/auth/me");
}
