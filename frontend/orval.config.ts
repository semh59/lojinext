import { defineConfig } from "orval";

export default defineConfig({
  // Target 1: React Query hooks + TypeScript types (tag başına dosya)
  lojinext: {
    input: {
      target: "./openapi.json",
      filters: {
        // auth: axios-instance 401 interceptor ile circular dep oluşturur
        // websocket: REST değil, hook üretilemez
        // internal: sefer_belge_yukle multipart, orval özel işlem gerektiriyor
        mode: "exclude",
        tags: ["auth", "websocket", "internal"],
      },
    },
    output: {
      mode: "tags-split",
      target: "./src/generated/api",
      schemas: "./src/generated/types",
      client: "react-query",
      httpClient: "axios",
      override: {
        mutator: {
          path: "./src/lib/orval-mutator.ts",
          name: "customAxiosInstance",
        },
        query: {
          useQuery: true,
          useMutation: true,
          useInfiniteScrollQuery: false,
        },
      },
    },
  },

  // Target 2: Zod şemaları (tüm component schemas, tek dosya)
  // includeUnreferencedSchemas=true → exclude edilen tag'lerin şemaları da gelir
  "lojinext-zod": {
    input: {
      target: "./openapi.json",
      filters: {
        includeUnreferencedSchemas: true,
      },
    },
    output: {
      client: "zod",
      target: "./src/generated/schemas.ts",
      mode: "single",
    },
  },
});
