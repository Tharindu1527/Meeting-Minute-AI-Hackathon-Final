import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useToast } from "../components/Toaster";
import { ApiError, api, getToken, isRemembered, setToken, setUnauthorizedHandler } from "./api";
import type { Session, User } from "./types";

interface AuthValue {
  /** The signed-in user; null when signed out */
  user: User | null;
  /** True while a stored session is being checked */
  checking: boolean;
  /** A stored session couldn't be checked because the server is unreachable */
  error: Error | null;
  retry: () => void;
  signIn: (session: Session, remember: boolean) => void;
  /** Swap in a fresh session (after a password change), keeping "Keep me signed in" as it was */
  replaceSession: (session: Session) => void;
  setUser: (user: User) => void;
  signOut: () => void;
}

const AuthContext = createContext<AuthValue | null>(null);

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside <AuthProvider>");
  return value;
}

/** The signed-in user (only call this inside the signed-in part of the app) */
export function useUser(): User {
  const { user } = useAuth();
  if (!user) throw new Error("useUser needs a signed-in user");
  return user;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const client = useQueryClient();
  const toast = useToast();
  const [token, setTokenState] = useState(getToken);
  const me = useQuery({ queryKey: ["me"], queryFn: api.me, enabled: Boolean(token), staleTime: Infinity, retry: false });

  // Drop everything cached for the previous user, but keep the public server status
  const forgetUserData = useCallback(
    () => client.removeQueries({ predicate: (query) => query.queryKey[0] !== "status" }),
    [client],
  );

  const signOut = useCallback(() => {
    setToken(null);
    forgetUserData();
    setTokenState(null);
  }, [forgetUserData]);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      forgetUserData();
      setTokenState(null);
      toast("info", "Please sign in again", "Your session ended, for example after a password change on another device.");
    });
    return () => setUnauthorizedHandler(null);
  }, [forgetUserData, toast]);

  const value = useMemo<AuthValue>(() => {
    const unauthorized = me.error instanceof ApiError && me.error.status === 401;
    return {
      user: token && me.data ? me.data : null,
      checking: Boolean(token) && me.isPending,
      error: token && me.isError && !unauthorized ? me.error : null,
      retry: () => void me.refetch(),
      signIn: (session, remember) => {
        forgetUserData();
        setToken(session.token, remember);
        client.setQueryData(["me"], session.user);
        setTokenState(session.token);
      },
      replaceSession: (session) => {
        setToken(session.token, isRemembered());
        client.setQueryData(["me"], session.user);
        setTokenState(session.token);
      },
      setUser: (user) => client.setQueryData(["me"], user),
      signOut,
    };
  }, [token, me, client, forgetUserData, signOut]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/** "Ana Silva" -> "AS", "ana@example.com" -> "A" */
export function initials(user: Pick<User, "name" | "email">): string {
  const words = (user.name || user.email).trim().split(/\s+/);
  return ((words[0]?.[0] ?? "") + (words.length > 1 ? (words[words.length - 1][0] ?? "") : "")).toUpperCase() || "?";
}

export function firstName(user: Pick<User, "name" | "email">): string {
  return (user.name || user.email.split("@")[0]).trim().split(/\s+/)[0];
}
