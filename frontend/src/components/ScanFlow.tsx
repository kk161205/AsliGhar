import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, createScan, type CreateScanInput } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import ScanningState from "./ScanningState";
import UploadForm from "./UploadForm";

type FlowState = { status: "form" } | { status: "scanning"; photoCount: number; done: boolean } | {
  status: "error";
  message: string;
};

export default function ScanFlow() {
  const [state, setState] = useState<FlowState>({ status: "form" });
  const navigate = useNavigate();
  const { state: authState } = useAuth();
  const defaultCity =
    authState.status === "authenticated" ? authState.user.city ?? undefined : undefined;

  async function handleSubmit(input: CreateScanInput) {
    setState({ status: "scanning", photoCount: input.photos.length, done: false });
    try {
      const result = await createScan(input);
      setState({ status: "scanning", photoCount: input.photos.length, done: true });
      navigate(`/scan/${result.scan_id}`);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Something went wrong. Try again.";
      setState({ status: "error", message });
    }
  }

  if (state.status === "scanning") {
    return <ScanningState photoCount={state.photoCount} complete={state.done} />;
  }

  return (
    <div>
      {state.status === "error" && (
        <p className="scan-flow__error" role="alert">
          {state.message}
        </p>
      )}
      <UploadForm onSubmit={handleSubmit} defaultCity={defaultCity} />
    </div>
  );
}
