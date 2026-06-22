import { beforeEach, describe, expect, it, vi } from "vitest";
import { tokenStorage, fetchWithAuth } from "../auth-service";

vi.mock("../../storage-service", () => {
  const store: Record<string, string> = {};
  return {
    storageService: {
      getItem: <T>(_key: string) => (store[_key] as T) ?? null,
      setItem: (_key: string, value: string) => {
        store[_key] = value;
      },
      removeItem: (_key: string) => {
        delete store[_key];
      },
    },
  };
});

describe("tokenStorage", () => {
  beforeEach(() => {
    tokenStorage.remove();
  });

  it("token set edilince get() döndürür", () => {
    tokenStorage.set("access-abc");
    expect(tokenStorage.get()).toBe("access-abc");
  });

  it("remove() sonrası get() null döndürür", () => {
    tokenStorage.set("token");
    tokenStorage.remove();
    expect(tokenStorage.get()).toBeNull();
  });

  it("set() access token kaydeder", () => {
    tokenStorage.set("access-only");
    expect(tokenStorage.get()).toBe("access-only");
  });
});

describe("fetchWithAuth", () => {
  beforeEach(() => {
    tokenStorage.remove();
    vi.restoreAllMocks();
  });

  it("başarılı istek response döndürür", async () => {
    const mockResponse = new Response(JSON.stringify({ ok: true }), {
      status: 200,
    });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(mockResponse));

    tokenStorage.set("my-token");
    const res = await fetchWithAuth("/test");
    expect(res.status).toBe(200);

    const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls;
    expect(calls[0][1].headers.get("Authorization")).toBe("Bearer my-token");
  });

  it("token yoksa Authorization header eklenmez", async () => {
    const mockResponse = new Response("{}", { status: 200 });
    const fetchMock = vi.fn().mockResolvedValue(mockResponse);
    vi.stubGlobal("fetch", fetchMock);

    await fetchWithAuth("/public");
    const headers: Headers = fetchMock.mock.calls[0][1].headers;
    expect(headers.get("Authorization")).toBeNull();
  });
});
