import { useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import {
  authFetch,
  getAccessToken,
  getStoredUser,
  logout as apiLogout,
  onAuthChange,
  type AuthUser,
} from "@/lib/auth-api";

type Profile = { id: string; full_name: string; bio: string | null; avatar_url: string | null };

type Session = {
  access_token: string;
  user: AuthUser;
};

type Ctx = {
  user: AuthUser | null;
  session: Session | null;
  profile: Profile | null;
  isAdmin: boolean;
  loading: boolean;
  refreshProfile: () => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<Ctx>({
  user: null,
  session: null,
  profile: null,
  isAdmin: false,
  loading: true,
  refreshProfile: async () => {},
  signOut: async () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [loading, setLoading] = useState(true);
  const queryClient = useQueryClient();

  useEffect(() => {
    setUser(getStoredUser());
    setLoading(false);
    return onAuthChange((next) => setUser(next));
  }, []);

  const load = useMemo(
    () => async () => {
      if (!user) {
        setProfile(null);
        setIsAdmin(false);
        return;
      }
      try {
        const res = await authFetch("/api/users/me/profile");
        if (!res.ok) {
          setProfile({ id: user.id, full_name: user.full_name ?? "", bio: null, avatar_url: null });
          setIsAdmin(false);
          return;
        }
        const data = (await res.json()) as Profile & { is_admin?: boolean };
        setProfile({
          id: data.id,
          full_name: data.full_name,
          bio: data.bio,
          avatar_url: data.avatar_url,
        });
        setIsAdmin(Boolean(data.is_admin));
      } catch {
        setProfile({ id: user.id, full_name: user.full_name ?? "", bio: null, avatar_url: null });
        setIsAdmin(false);
      }
    },
    [user],
  );

  useEffect(() => {
    void load();
  }, [load]);

  const session = useMemo<Session | null>(() => {
    const token = getAccessToken();
    if (!user || !token) return null;
    return { access_token: token, user };
  }, [user]);

  const value = useMemo<Ctx>(
    () => ({
      user,
      session,
      profile,
      isAdmin,
      loading,
      refreshProfile: load,
      signOut: async () => {
        await queryClient.cancelQueries();
        queryClient.clear();
        await apiLogout();
      },
    }),
    [user, session, profile, isAdmin, loading, load, queryClient],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
