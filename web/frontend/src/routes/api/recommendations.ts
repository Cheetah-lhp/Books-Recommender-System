import { createFileRoute } from "@tanstack/react-router";

/**
 * Thin proxy to FastAPI recommender. Scoring lives in Python
 * (web/backend/app/services/recommender.py), not in Node.
 */
const API_BASE = process.env["API_BASE"] || process.env["VITE_API_URL"] || "http://127.0.0.1:8000";

async function proxy(request: Request): Promise<Response> {
  const incoming = new URL(request.url);
  const target = new URL("/api/recommendations", API_BASE);
  target.search = incoming.search;

  const headers = new Headers();
  const auth = request.headers.get("authorization");
  if (auth) headers.set("authorization", auth);
  headers.set("content-type", "application/json");

  try {
    const init: RequestInit = {
      method: request.method,
      headers,
      signal: AbortSignal.timeout(15_000),
    };
    if (request.method !== "GET" && request.method !== "HEAD") {
      init.body = await request.text();
    }
    const res = await fetch(target, init);
    const body = await res.text();
    return new Response(body, {
      status: res.status,
      headers: { "content-type": res.headers.get("content-type") ?? "application/json" },
    });
  } catch (error) {
    console.error("recommendations proxy failed", error);
    return Response.json({ books: [] }, { status: 200 });
  }
}

export const Route = createFileRoute("/api/recommendations")({
  server: {
    handlers: {
      GET: ({ request }) => proxy(request),
      POST: ({ request }) => proxy(request),
    },
  },
});
