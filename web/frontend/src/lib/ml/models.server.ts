/**
 * READORA ML model registry (server-side only).
 *
 * Discover recommendations are produced by FastAPI calling the hybrid model
 * service (ALS + TF-IDF content + popularity). Optional sentiment/query URLs
 * remain stubs. There is no in-app heuristic recommender fallback.
 */

export type MlModelKey = "recommender" | "sentiment" | "query";

const ENV_KEYS: Record<MlModelKey, string> = {
  recommender: "ML_RECOMMENDER_URL",
  sentiment: "ML_SENTIMENT_URL",
  query: "ML_QUERY_URL",
};

export function modelUrl(key: MlModelKey): string | null {
  // Legacy variable kept working for the recommender service.
  const direct = process.env[ENV_KEYS[key]];
  if (direct) return direct;
  if (key === "recommender") return process.env["RECOMMENDER_API_URL"] ?? null;
  return null;
}

export function modelStatus() {
  return (Object.keys(ENV_KEYS) as MlModelKey[]).map((key) => ({
    model: key,
    connected: Boolean(modelUrl(key)),
  }));
}

/** POST a payload to a configured model service. Returns null when unavailable. */
export async function callModel<T>(key: MlModelKey, payload: unknown, timeoutMs = 8000): Promise<T | null> {
  const url = modelUrl(key);
  if (!url) return null;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const headers: Record<string, string> = { "content-type": "application/json" };
    const token = process.env["ML_API_KEY"];
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const res = await fetch(url, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}
