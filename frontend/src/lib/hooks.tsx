import { useQuery } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "./api";
import type { AppStatus, Job } from "./types";

const MODEL_KEY = "meeting-minutes-model";

const ModelContext = createContext<{ model: string; setModel: (model: string) => void }>({
  model: "",
  setModel: () => {},
});

/** The Gemini model chosen in the sidebar, remembered in this browser */
export function ModelProvider({ status, children }: { status: AppStatus; children: ReactNode }) {
  const [model, setModel] = useState(() => {
    try {
      const saved = localStorage.getItem(MODEL_KEY);
      if (saved && status.models.includes(saved)) return saved;
    } catch {
      // Storage unavailable: fall back to the server default
    }
    return status.default_model;
  });
  useEffect(() => {
    try {
      localStorage.setItem(MODEL_KEY, model);
    } catch {
      // Not remembered across visits; the choice still applies now
    }
  }, [model]);
  return <ModelContext.Provider value={{ model, setModel }}>{children}</ModelContext.Provider>;
}

export const useModel = () => useContext(ModelContext);

export function useStatus() {
  return useQuery({ queryKey: ["status"], queryFn: api.status, staleTime: 30_000 });
}

/** Poll a background job until it finishes */
export function useJob<T>(jobId: string | null) {
  return useQuery({
    queryKey: ["job", jobId],
    queryFn: () => api.job<T>(jobId as string),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const job = query.state.data as Job<T> | undefined;
      return !job || job.status === "running" ? 1500 : false;
    },
  });
}

/** An object URL for a Blob, revoked when it changes or the component unmounts */
export function useObjectUrl(blob: Blob | null) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!blob) {
      setUrl(null);
      return;
    }
    const next = URL.createObjectURL(blob);
    setUrl(next);
    return () => URL.revokeObjectURL(next);
  }, [blob]);
  return url;
}
