/** Local JWT auth client replacing Supabase Auth. */

const ACCESS_KEY = "brs_access_token";
const REFRESH_KEY = "brs_refresh_token";
const USER_KEY = "brs_user";

export type AuthUser = {
  id: string;
  email: string;
  full_name?: string | null;
};

type TokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: AuthUser;
};

type Listener = (user: AuthUser | null) => void;
const listeners = new Set<Listener>();

function notify(user: AuthUser | null) {
  listeners.forEach((l) => l(user));
}

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ACCESS_KEY);
}

export function getStoredUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

function persist(tokens: TokenResponse) {
  localStorage.setItem(ACCESS_KEY, tokens.access_token);
  localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
  localStorage.setItem(USER_KEY, JSON.stringify(tokens.user));
  notify(tokens.user);
}

export function clearSession() {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
  localStorage.removeItem(USER_KEY);
  notify(null);
}

export function onAuthChange(listener: Listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: {
      "content-type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export async function register(email: string, password: string, fullName = "") {
  const data = await api<TokenResponse>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, full_name: fullName }),
  });
  persist(data);
  return data;
}

export async function login(email: string, password: string) {
  const data = await api<TokenResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  persist(data);
  return data;
}

export async function logout() {
  const refresh = typeof window !== "undefined" ? localStorage.getItem(REFRESH_KEY) : null;
  if (refresh) {
    try {
      await api("/api/auth/logout", {
        method: "POST",
        body: JSON.stringify({ refresh_token: refresh }),
      });
    } catch {
      /* ignore */
    }
  }
  clearSession();
}

export async function authFetch(input: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers);
  let token = getAccessToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  let res = await fetch(input, { ...init, headers });

  // Tu dong lam moi token neu gap 401
  if (res.status === 401 && typeof window !== "undefined") {
    const refresh = localStorage.getItem(REFRESH_KEY);
    if (refresh) {
      try {
        const refreshRes = await fetch("/api/auth/refresh", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ refresh_token: refresh }),
        });
        if (refreshRes.ok) {
          const data = (await refreshRes.json()) as TokenResponse;
          persist(data);
          token = data.access_token;
          headers.set("Authorization", `Bearer ${token}`);
          res = await fetch(input, { ...init, headers });
        } else {
          clearSession();
        }
      } catch {
        clearSession();
      }
    } else {
      clearSession();
    }
  }

  // Ghi log ho tro kiem tra he thong
  if (typeof input === "string" && (input.includes("/api/library") || input.includes("/api/auth") || input.includes("/api/users/me"))) {
    fetch("http://127.0.0.1:7460/ingest/b819d754-3046-494d-a58c-7e31ffe6c52a", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Debug-Session-Id": "829bc3" },
      body: JSON.stringify({
        sessionId: "829bc3",
        runId: "pre-fix",
        hypothesisId: "A",
        location: "auth-api.ts:authFetch",
        message: "authFetch result",
        data: {
          path: input,
          method: init.method ?? "GET",
          hasToken: Boolean(token),
          tokenLen: token?.length ?? 0,
          status: res.status,
          hasStoredUser: Boolean(getStoredUser()),
        },
        timestamp: Date.now(),
      }),
    }).catch(() => {});
  }
  return res;
}
