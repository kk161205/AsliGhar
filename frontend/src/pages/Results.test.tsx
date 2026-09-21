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

const signal = { score: 0, max: 10, finding: "ok", status: "ok" as const, sources: [], basis: "indicator" as const };
const SCAN: ScanResponse = {
  scan_id: "abc",
  risk_score: 12,
  risk_band: "Low",
  signals: { image_reuse: signal, price_deviation: signal, address_validity: signal },
  evidence: [],
  ai_summary: null,
  created_at: "2026-09-21T00:00:00Z",
  partial: false,
  checks_run: 3,
  checks_total: 3,
  insights: [],
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
        photos: [],
      },
    });

    expect(await screen.findByText("How we searched")).toBeInTheDocument();
  });
});

describe("Results coverage, evidence and insights", () => {
  it("says all checks ran when none was unavailable", async () => {
    renderResults(SCAN);
    expect(await screen.findByText("All 3 checks ran.")).toBeInTheDocument();
  });

  it("says how many checks ran when some could not", async () => {
    renderResults({ ...SCAN, partial: true, checks_run: 2 });
    expect(await screen.findByRole("note")).toHaveTextContent("2 of 3 checks ran");
  });

  it("shows the reasons, the page's own words, how it was identified and the exact link", async () => {
    renderResults({
      ...SCAN,
      evidence: [
        {
          type: "image_match",
          photo_index: 0,
          photo_indexes: [0, 2],
          source_domain: "olx.in",
          source_url: "https://www.olx.in/item/for-sale-x-iid-1",
          source_title: "3BHK house for sale in Agra",
          listed_price: 3199000,
          submitted_price: 15000,
          listed_city: "Agra",
          submitted_city: "Bengaluru",
          reasons: ["It is a listing for sale, but you submitted a rental. It shows ₹31,99,000."],
          listing_type: "sale",
          source_snippet: "3 BHK - 3 Bathroom - 800 sqft. ₹ 31,99,000.",
          tier: "proven",
          matched_by: ["photo 1", "photo 3"],
        },
      ],
    });

    expect(await screen.findByText(/Photos 1 and 3 also appear on/)).toBeInTheDocument();
    expect(screen.getByText("Proven", { selector: ".tier" })).toBeInTheDocument();
    expect(screen.getByText(/It is a listing for sale, but you submitted a rental/)).toBeInTheDocument();
    expect(screen.getByText(/Identified as the same home by: photo 1, photo 3/)).toBeInTheDocument();
    expect(screen.getByText(/3 BHK - 3 Bathroom - 800 sqft/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open the page" })).toHaveAttribute(
      "href",
      "https://www.olx.in/item/for-sale-x-iid-1",
    );
  });

  it("still describes an older stored item that has no reasons", async () => {
    renderResults({
      ...SCAN,
      evidence: [
        {
          type: "image_match",
          photo_index: 1,
          source_domain: "olx.in",
          source_url: "https://www.olx.in/item/x-iid-2",
          source_title: "Flat in Pune",
          listed_price: 9500,
          submitted_price: 15000,
          listed_city: "Pune",
          submitted_city: "Bengaluru",
        } as ScanResponse["evidence"][number],
      ],
    });

    expect(await screen.findByText(/Photo 2 also appears on/)).toBeInTheDocument();
    expect(screen.getByText(/Listed at ₹9,500 in Pune, versus your submitted ₹15,000 in Bengaluru/)).toBeInTheDocument();
  });

  it("lists the insights with their tier and link, and says they don't change the score", async () => {
    renderResults({
      ...SCAN,
      insights: [
        {
          kind: "listing_link",
          tier: "proven",
          title: "This link is a sale listing",
          detail: "You entered a rent, but the page is for sale.",
          url: "https://www.olx.in/item/for-sale-x-iid-1",
        },
        {
          kind: "phone",
          tier: "indicator",
          title: "Nothing found for this number",
          detail: "A search for the number found no fraud reports.",
          url: null,
        },
      ],
    });

    expect(await screen.findByText("Also worth knowing")).toBeInTheDocument();
    expect(screen.getByText("This link is a sale listing")).toBeInTheDocument();
    expect(screen.getByText("Nothing found for this number")).toBeInTheDocument();
    expect(screen.getByText("These don't change the score.")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Open the page" })).toHaveLength(1);
  });

  it("shows what a signal is based on, with links", async () => {
    const withSources = {
      ...signal,
      score: 30,
      basis: "indicator" as const,
      sources: [
        { title: "2 BHK Flats for Rent", url: "https://example.com/rent/1", detail: "₹28,000 a month — “quote”" },
        { title: "No link here", url: null, detail: "₹30,000 a month" },
      ],
    };
    renderResults({ ...SCAN, signals: { ...SCAN.signals, price_deviation: withSources } });

    expect(await screen.findByText("What this is based on (2)")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "2 BHK Flats for Rent" })).toHaveAttribute("href", "https://example.com/rent/1");
    expect(screen.getByText("No link here")).toBeInTheDocument();
  });
});
