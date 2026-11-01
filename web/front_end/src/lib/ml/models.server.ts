/**
 * READORA ML model registry.
 *
 * The project uses three separate ML models. Each one is a standalone service
 * reached over HTTP from the backend — never executed in the browser. When a
 * model URL is not configured the backend falls back to its deterministic
 * in-app heuristic so the product keeps working.
 *
 *   READORA frontend
 *        -> backend / API (server functions + /api routes)
 *              -> ML model 1: recommender      (ML_RECOMMENDER_URL)
 *              -> ML model 2: review sentiment (ML_SENTIMENT_URL)
 *              -> ML model 3: query understanding (ML_QUERY_URL)
 *        -> recommendation engine
 *   -> personalized recommendations
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
export type ModelCall<T> = {
  data: T | null;
  status: "used" | "unconfigured" | "unavailable";
  durationMs: number;
};

export async function callModelWithStatus<T>(
  key: MlModelKey,
  payload: unknown,
  timeoutMs = 8000,
): Promise<ModelCall<T>> {
  const url = modelUrl(key);
  if (!url) return { data: null, status: "unconfigured", durationMs: 0 };
  const started = performance.now();
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
    if (!res.ok)
      return { data: null, status: "unavailable", durationMs: performance.now() - started };
    return {
      data: (await res.json()) as T,
      status: "used",
      durationMs: performance.now() - started,
    };
  } catch {
    return { data: null, status: "unavailable", durationMs: performance.now() - started };
  } finally {
    clearTimeout(timer);
  }
}

export async function callModel<T>(
  key: MlModelKey,
  payload: unknown,
  timeoutMs = 8000,
): Promise<T | null> {
  return (await callModelWithStatus<T>(key, payload, timeoutMs)).data;
}
