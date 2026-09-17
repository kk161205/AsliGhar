export type RiskBand = "Low" | "Moderate" | "High" | "Severe";

export interface SignalResult {
  score: number;
  max: number;
  finding: string;
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

export interface ScanResponse {
  scan_id: string;
  risk_score: number;
  risk_band: RiskBand;
  signals: ScanSignals;
  evidence: ImageMatchEvidence[];
  ai_summary: string | null;
  created_at: string;
}

export interface ApiErrorBody {
  detail: string | { type: string; loc: (string | number)[]; msg: string }[];
}
