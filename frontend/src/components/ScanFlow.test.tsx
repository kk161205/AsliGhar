import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as client from "../api/client";
import type { GateResult, ScanResponse } from "../api/types";
import ScanFlow from "./ScanFlow";

vi.mock("../api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/client")>()),
  precheckRent: vi.fn(),
  createScan: vi.fn(),
}));
vi.mock("../auth/AuthContext", () => ({ useAuth: () => ({ state: { status: "anonymous" } }) }));

const precheckRent = vi.mocked(client.precheckRent);
const createScan = vi.mocked(client.createScan);

const OK: GateResult = { status: "ok", issues: [] };
const UNUSUAL: GateResult = {
  status: "needs_confirmation",
  issues: [{ code: "rent_unusually_low", field: "rent", message: "₹1,500 a month is unusually low for a rental." }],
};
const IMPOSSIBLE: GateResult = {
  status: "rejected",
  issues: [{ code: "rent_impossible", field: "rent", message: "₹50 a month isn't a possible rent." }],
};

function renderFlow() {
  return render(
    <MemoryRouter initialEntries={["/scan"]}>
      <Routes>
        <Route path="/scan" element={<ScanFlow />} />
        <Route path="/scan/:id" element={<p>result page</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

async function fillForm(user: ReturnType<typeof userEvent.setup>, rent: string) {
  const photo = new File(["x"], "room.jpg", { type: "image/jpeg" });
  await user.upload(screen.getByLabelText("Upload listing photos"), photo);
  await user.type(screen.getByLabelText(/^address/i), "Indiranagar");
  await user.type(screen.getByLabelText(/^city/i), "Bengaluru");
  await user.type(screen.getByLabelText(/monthly rent/i), rent);
}

beforeEach(() => {
  precheckRent.mockReset();
  createScan.mockReset();
  createScan.mockResolvedValue({ scan_id: "abc" } as ScanResponse);
});

describe("rent pre-check", () => {
  it("scans straight away when the rent is fine", async () => {
    precheckRent.mockResolvedValue(OK);
    const user = userEvent.setup();
    renderFlow();
    await fillForm(user, "25000");

    await user.click(screen.getByRole("button", { name: "Check this listing" }));

    expect(await screen.findByText("result page")).toBeInTheDocument();
    expect(precheckRent).toHaveBeenCalledWith(25000);
    expect(createScan).toHaveBeenCalledTimes(1);
    expect(createScan.mock.calls[0][0].overrideReason).toBeUndefined();
  });

  it("refuses an impossible rent without scanning and keeps what was typed", async () => {
    precheckRent.mockResolvedValue(IMPOSSIBLE);
    const user = userEvent.setup();
    renderFlow();
    await fillForm(user, "50");

    await user.click(screen.getByRole("button", { name: "Check this listing" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("isn't a possible rent");
    expect(createScan).not.toHaveBeenCalled();
    expect(screen.getByLabelText(/^address/i)).toHaveValue("Indiranagar");
  });

  it("asks for a reason on an unusual rent and sends it with the scan", async () => {
    precheckRent.mockResolvedValue(UNUSUAL);
    const user = userEvent.setup();
    renderFlow();
    await fillForm(user, "1500");

    await user.click(screen.getByRole("button", { name: "Check this listing" }));

    expect(await screen.findByText(/unusually low/)).toBeInTheDocument();
    expect(createScan).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Scan anyway" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("at least 10 characters");
    expect(createScan).not.toHaveBeenCalled();

    await user.type(screen.getByLabelText(/why is this rent right/i), "Single room in a family home");
    await user.click(screen.getByRole("button", { name: "Scan anyway" }));

    expect(await screen.findByText("result page")).toBeInTheDocument();
    expect(createScan).toHaveBeenCalledTimes(1);
    expect(createScan.mock.calls[0][0].overrideReason).toBe("Single room in a family home");
  });

  it("drops the question when the rent is changed afterwards", async () => {
    precheckRent.mockResolvedValueOnce(UNUSUAL).mockResolvedValueOnce(OK);
    const user = userEvent.setup();
    renderFlow();
    await fillForm(user, "1500");
    await user.click(screen.getByRole("button", { name: "Check this listing" }));
    await screen.findByText(/unusually low/);

    await user.clear(screen.getByLabelText(/monthly rent/i));
    await user.type(screen.getByLabelText(/monthly rent/i), "20000");

    expect(screen.queryByText(/unusually low/)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Check this listing" }));
    expect(await screen.findByText("result page")).toBeInTheDocument();
    expect(createScan.mock.calls[0][0].overrideReason).toBeUndefined();
  });

  it("still scans if the pre-check can't be reached, leaving the server to decide", async () => {
    precheckRent.mockRejectedValue(new client.ApiError("offline"));
    const user = userEvent.setup();
    renderFlow();
    await fillForm(user, "25000");

    await user.click(screen.getByRole("button", { name: "Check this listing" }));

    await waitFor(() => expect(createScan).toHaveBeenCalledTimes(1));
  });

  it("brings the form back intact when the scan itself fails", async () => {
    precheckRent.mockResolvedValue(OK);
    createScan.mockRejectedValue(new client.ApiError("Photo room.jpg exceeds 5MB."));
    const user = userEvent.setup();
    renderFlow();
    await fillForm(user, "25000");

    await user.click(screen.getByRole("button", { name: "Check this listing" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("exceeds 5MB");
    expect(screen.getByLabelText(/^address/i)).toHaveValue("Indiranagar");
    expect(screen.getByAltText("Listing photo 1")).toBeInTheDocument();
  });
});
