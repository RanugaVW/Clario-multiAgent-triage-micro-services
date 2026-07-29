import { http, HttpResponse } from "msw";

/** Shared API defaults. Feature tests override these when testing error paths. */
export const handlers = [
  http.get("/api/health", () => HttpResponse.json({ status: "ok" })),
];
