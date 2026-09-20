import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, createScan, precheckRent, type CreateScanInput } from "../api/client";
import type { GateResult } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import ScanningState from "./ScanningState";
import UploadForm, { type RentConfirmation } from "./UploadForm";

type FlowState =
  | { status: "form" }
  | { status: "checking" }
  | { status: "scanning"; photoCount: number; done: boolean };

export default function ScanFlow() {
  const [flow, setFlow] = useState<FlowState>({ status: "form" });
  const [error, setError] = useState<string | null>(null);
  const [confirmation, setConfirmation] = useState<RentConfirmation | null>(null);
  const navigate = useNavigate();
  const { state: authState } = useAuth();
  const defaultCity =
    authState.status === "authenticated" ? authState.user.city ?? undefined : undefined;

  async function runScan(input: CreateScanInput) {
    setFlow({ status: "scanning", photoCount: input.photos.length, done: false });
    try {
      const result = await createScan(input);
      setFlow({ status: "scanning", photoCount: input.photos.length, done: true });
      navigate(`/scan/${result.scan_id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
      setFlow({ status: "form" });
    }
  }

  async function handleSubmit(input: CreateScanInput) {
    setError(null);
    if (input.overrideReason === undefined) {
      setFlow({ status: "checking" });
      // If the free pre-check can't be reached, go ahead: the scan endpoint
      // applies the same rules and answers with the reason it refused.
      const gate: GateResult | null = await precheckRent(input.rent).catch(() => null);
      if (gate?.status === "rejected") {
        setError(gate.issues[0].message);
        setFlow({ status: "form" });
        return;
      }
      if (gate?.status === "needs_confirmation") {
        setConfirmation({ rent: input.rent, message: gate.issues[0].message });
        setFlow({ status: "form" });
        return;
      }
    }
    await runScan(input);
  }

  return (
    <div>
      {flow.status === "scanning" && (
        <ScanningState photoCount={flow.photoCount} complete={flow.done} />
      )}
      {/* Kept mounted while scanning so a failed scan leaves the form as it was. */}
      <div hidden={flow.status === "scanning"}>
        {error && (
          <p className="scan-flow__error" role="alert">
            {error}
          </p>
        )}
        <UploadForm
          onSubmit={handleSubmit}
          defaultCity={defaultCity}
          busy={flow.status === "checking"}
          confirmation={confirmation}
        />
      </div>
    </div>
  );
}
