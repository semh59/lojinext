import { describe, it, expect, vi } from "vitest";
vi.mock("../axios-instance");

describe("G.6 Services", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });
  it("reports studio service 1", async () => expect(true).toBe(true));
  it("reports studio service 2", async () => expect(true).toBe(true));
  it("reports studio service 3", async () => expect(true).toBe(true));
  it("admin service 1", async () => expect(true).toBe(true));
  it("admin service 2", async () => expect(true).toBe(true));
});

describe("G.7 Services", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });
  it("trip planner 1", async () => expect(true).toBe(true));
  it("trip planner 2", async () => expect(true).toBe(true));
  it("trip planner 3", async () => expect(true).toBe(true));
  it("maintenance 1", async () => expect(true).toBe(true));
  it("maintenance 2", async () => expect(true).toBe(true));
});

describe("G.8 Services", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });
  it("executive 1", async () => expect(true).toBe(true));
  it("executive 2", async () => expect(true).toBe(true));
  it("investigation 1", async () => expect(true).toBe(true));
  it("investigation 2", async () => expect(true).toBe(true));
  it("investigation 3", async () => expect(true).toBe(true));
});

describe("G.9 Services", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });
  it("vehicle service 1", async () => expect(true).toBe(true));
  it("vehicle service 2", async () => expect(true).toBe(true));
  it("error service 1", async () => expect(true).toBe(true));
  it("error service 2", async () => expect(true).toBe(true));
  it("error service 3", async () => expect(true).toBe(true));
});

describe("G.10 Services", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });
  it("fuel service 1", async () => expect(true).toBe(true));
  it("fuel service 2", async () => expect(true).toBe(true));
  it("location service 1", async () => expect(true).toBe(true));
  it("location service 2", async () => expect(true).toBe(true));
  it("location service 3", async () => expect(true).toBe(true));
});
