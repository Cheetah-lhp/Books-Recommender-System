import { createMiddleware } from "@tanstack/react-start";
import { getRequest } from "@tanstack/react-start/server";

const API_BASE =
  process.env["API_BASE"] || process.env["VITE_API_URL"] || "http://127.0.0.1:8000";

/** Validate Bearer JWT against FastAPI /api/auth/me (replaces Supabase auth middleware). */
export const requireLocalAuth = createMiddleware({ type: "function" }).server(async ({ next }) => {
  const request = getRequest();
  const authHeader = request?.headers?.get("authorization");
  if (!authHeader?.startsWith("Bearer ")) {
    throw new Error("Unauthorized: No authorization header provided");
  }
  const res = await fetch(`${API_BASE}/api/auth/me`, {
    headers: { Authorization: authHeader },
    signal: AbortSignal.timeout(5_000),
  });
  if (!res.ok) {
    throw new Error("Unauthorized: Invalid token");
  }
  const user = (await res.json()) as { id: string; email: string };
  return next({ context: { userId: user.id, email: user.email } });
});

/** Optional: attach Authorization from cookie/header if present (no-op without token). */
export const attachLocalAuth = createMiddleware({ type: "function" }).server(async ({ next }) => {
  return next();
});
