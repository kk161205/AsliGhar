import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import * as client from "../api/client";
import type { ScanResponse } from "../api/types";
import Results from "./Results";

vi.mock("../components/Nav", () => ({ default: () => null }));
vi.mock("../api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/client")>()),
  getScan: vi.fn(),
}));

const signal = { score: 0, max: 10, finding: "ok", status: "ok" as const };
const SCAN: ScanResponse = {
  scan_id: "abc",
  risk_score: 12,
  risk_band: "Low",
  signals: { image_reuse: signal, price_deviation: signal, address_validity: signal },
  evidence: [],
  ai_summary: null,
  created_at: "2026-09-21T00:00:00Z",
  partial: false,
  override_reason: null,
  search_trace: null,
};

function renderResults(scan: ScanResponse) {
  vi.mocked(client.getScan).mockResolvedValue(scan);
  return render(
    <MemoryRouter initialEntries={["/scan/abc"]}>
      <Routes>
        <Route path="/scan/:scanId" element={<Results />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("Results", () => {
  it("shows the reason given for an unusual rent and says it doesn't change the score", async () => {
    renderResults({ ...SCAN, override_reason: "Single room in a family home" });

    expect(await screen.findByRole("note")).toHaveTextContent("Single room in a family home");
    expect(screen.getByRole("note")).toHaveTextContent("doesn't change the score");
  });

  it("shows neither the override note nor the search trace for older scans", async () => {
    renderResults(SCAN);

    await screen.findByText("Scan result");
    expect(screen.queryByRole("note")).not.toBeInTheDocument();
    expect(screen.queryByText("How we searched")).not.toBeInTheDocument();
  });

  it("offers the search trace when the scan has one", async () => {
    renderResults({
      ...SCAN,
      search_trace: {
        reviewer_used: true,
        understood: { address_city: null, locality: "Koramangala", landmark: null, pincode: null, bhk: null },
        queries: [{ check: "price", query: "rent Koramangala Bengaluru price" }],
      },
    });

    expect(await screen.findByText("How we searched")).toBeInTheDocument();
  });
});
