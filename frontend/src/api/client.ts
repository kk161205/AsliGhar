import type { ApiErrorBody, GateResult, ScanResponse, ScanSummary, User } from "./types";

export class ApiError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ApiError";
  }
}

function messageFromErrorBody(body: ApiErrorBody): string {
  if (typeof body.detail === "string") {
    return body.detail;
  }
  return body.detail.map((item) => item.msg).join("; ");
}

async function parseErrorResponse(response: Response): Promise<never> {
  let message = `Request failed with status ${response.status}`;
  try {
    const body = (await response.json()) as ApiErrorBody;
    message = messageFromErrorBody(body);
  } catch {
    // response body wasn't JSON (e.g. a proxy/network error page) — keep the status message
  }
  throw new ApiError(message);
}

export interface CreateScanInput {
  photos: File[];
  address: string;
  city: string;
  rent: number;
  bhk?: string;
  description?: string;
  // Why an unusual rent is right; only sent once the user has been asked.
  overrideReason?: string;
}

export async function createScan(input: CreateScanInput): Promise<ScanResponse> {
  const formData = new FormData();
  for (const photo of input.photos) {
    formData.append("photos", photo);
  }
  formData.append("address", input.address);
  formData.append("city", input.city);
  formData.append("rent", String(input.rent));
  if (input.bhk) formData.append("bhk", input.bhk);
  if (input.description) formData.append("description", input.description);
  if (input.overrideReason) formData.append("override_reason", input.overrideReason);

  const response = await fetch("/api/v1/scan", {
    method: "POST",
    body: formData,
    credentials: "include",
  });
  if (!response.ok) {
    await parseErrorResponse(response);
  }
  return (await response.json()) as ScanResponse;
}

export async function getScan(scanId: string): Promise<ScanResponse> {
  const response = await fetch(`/api/v1/scan/${encodeURIComponent(scanId)}`);
  if (!response.ok) {
    await parseErrorResponse(response);
  }
  return (await response.json()) as ScanResponse;
}

export async function listScans(): Promise<ScanSummary[]> {
  const response = await fetch("/api/v1/scans", { credentials: "include" });
  if (!response.ok) {
    await parseErrorResponse(response);
  }
  return (await response.json()) as ScanSummary[];
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    await parseErrorResponse(response);
  }
  return (await response.json()) as T;
}

export function precheckRent(rent: number): Promise<GateResult> {
  return postJson<GateResult>("/api/v1/scan/precheck", { rent });
}

export interface SignupInput {
  email: string;
  password: string;
  fullName: string;
  city: string;
}

export function signup(input: SignupInput): Promise<User> {
  return postJson<User>("/api/v1/auth/signup", {
    email: input.email,
    password: input.password,
    full_name: input.fullName,
    city: input.city,
  });
}

export function login(email: string, password: string): Promise<User> {
  return postJson<User>("/api/v1/auth/login", { email, password });
}

export async function logout(): Promise<void> {
  await fetch("/api/v1/auth/logout", { method: "POST", credentials: "include" });
}

export async function getCurrentUser(): Promise<User | null> {
  const response = await fetch("/api/v1/auth/me", { credentials: "include" });
  if (response.status === 401) return null;
  if (!response.ok) {
    await parseErrorResponse(response);
  }
  return (await response.json()) as User;
}
