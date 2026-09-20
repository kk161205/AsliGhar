export type RiskBand = "Low" | "Moderate" | "High" | "Severe";

export interface SignalResult {
  score: number;
  max: number;
  finding: string;
  // "unavailable": the check couldn't run — not the same as a clean 0.
  status: "ok" | "unavailable";
}

export interface ScanSignals {
  image_reuse: SignalResult;
  price_deviation: SignalResult;
  address_validity: SignalResult;
}

export interface ImageMatchEvidence {
  type: "image_match";
  photo_index: number;
  source_domain: string;
  source_url: string;
  source_title: string;
  listed_price: number | null;
  submitted_price: number;
  listed_city: string | null;
  submitted_city: string;
}

export interface UnderstoodInput {
  address_city: string | null;
  locality: string | null;
  landmark: string | null;
  pincode: string | null;
  bhk: string | null;
}

export interface SearchTrace {
  // false when the address couldn't be read and plain city-level searches ran.
  reviewer_used: boolean;
  understood: UnderstoodInput;
  queries: { check: "address" | "price"; query: string }[];
}

export interface GateIssue {
  code: "rent_impossible" | "rent_unusually_low" | "rent_unusually_high";
  field: "rent";
  message: string;
}

export interface GateResult {
  status: "ok" | "needs_confirmation" | "rejected";
  issues: GateIssue[];
}

export interface ScanResponse {
  scan_id: string;
  risk_score: number;
  risk_band: RiskBand;
  signals: ScanSignals;
  evidence: ImageMatchEvidence[];
  ai_summary: string | null;
  created_at: string;
  partial: boolean;
  override_reason: string | null;
  search_trace: SearchTrace | null;
}

export interface ScanSummary {
  scan_id: string;
  address: string;
  city: string;
  risk_score: number;
  risk_band: RiskBand;
  created_at: string;
}

export interface ApiErrorBody {
  detail: string | { type: string; loc: (string | number)[]; msg: string }[];
}

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  city: string | null;
  created_at: string;
}
