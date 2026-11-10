/**
 * API client giao tiep voi backend Python API
 */

export const BACKEND_URL =
  (typeof process !== "undefined" ? process.env["VITE_API_URL"] : undefined) ||
  "http://127.0.0.1:8000";

export function getApiUrl(path: string): string {
  const clean = path.startsWith("/") ? path : `/${path}`;
  const fullPath = clean.startsWith("/api") ? clean : `/api${clean}`;
  if (typeof window === "undefined") {
    return `${BACKEND_URL}${fullPath}`;
  }
  return fullPath;
}

export async function apiFetch<T>(path: string): Promise<T> {
  const url = getApiUrl(path);
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
    return (await res.json()) as Promise<T>;
  } catch (err) {
    console.error(`[BRS Data] apiFetch error for ${url}:`, err);
    throw err;
  }
}

