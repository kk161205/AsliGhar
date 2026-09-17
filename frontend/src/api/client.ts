import type { ApiErrorBody, ScanResponse } from "./types";

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

  const response = await fetch("/api/v1/scan", { method: "POST", body: formData });
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
