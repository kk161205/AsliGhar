import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { SearchTrace } from "../api/types";
import HowWeSearched from "./HowWeSearched";

const TRACE: SearchTrace = {
  reviewer_used: true,
  understood: { address_city: "Bengaluru", locality: "Koramangala", landmark: null, pincode: null, bhk: "2BHK" },
  queries: [
    { check: "address", query: "flat 302 koramangala blr" },
    { check: "price", query: "2BHK rent Koramangala Bengaluru price" },
  ],
};

describe("HowWeSearched", () => {
  it("shows what was understood and the exact searches run", () => {
    render(<HowWeSearched trace={TRACE} />);

    expect(screen.getByText(/We read your address/)).toBeInTheDocument();
    expect(screen.getByText("Koramangala")).toBeInTheDocument();
    expect(screen.getByText("2BHK")).toBeInTheDocument();
    expect(screen.queryByText("Landmark")).not.toBeInTheDocument();
    expect(screen.getByText("flat 302 koramangala blr")).toBeInTheDocument();
    expect(screen.getByText("2BHK rent Koramangala Bengaluru price")).toBeInTheDocument();
  });

  it("says plainly when the address couldn't be read", () => {
    render(
      <HowWeSearched
        trace={{
          ...TRACE,
          reviewer_used: false,
          understood: { address_city: null, locality: null, landmark: null, pincode: null, bhk: null },
        }}
      />,
    );

    expect(screen.getByText(/compared across the whole city/)).toBeInTheDocument();
    expect(screen.queryByText("Area")).not.toBeInTheDocument();
  });
});
