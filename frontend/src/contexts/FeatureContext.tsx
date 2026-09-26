"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { apiGet } from "@/lib/api";

export type FeatureDecision = {
  key: string;
  label: string;
  allowed: boolean;
  release_allowed: boolean;
  entitlement_allowed: boolean;
  org_config_allowed: boolean;
  permission_allowed: boolean;
  org_configurable: boolean;
};

type FeaturePayload = {
  flags: Record<string, boolean>;
  features: FeatureDecision[];
};

type FeatureState = {
  flags: Record<string, boolean>;
  features: FeatureDecision[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
};

const FeatureContext = createContext<FeatureState | null>(null);

export function FeatureProvider({ children }: { children: ReactNode }) {
  const [flags, setFlags] = useState<Record<string, boolean>>({});
  const [features, setFeatures] = useState<FeatureDecision[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const payload = (await apiGet("/api/features/me")) as FeaturePayload;
      setFlags(payload.flags || {});
      setFeatures(payload.features || []);
    } catch (err) {
      setFlags({});
      setFeatures([]);
      setError(err instanceof Error ? err.message : "Could not load features.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const value = useMemo(
    () => ({ flags, features, loading, error, refresh }),
    [flags, features, loading, error, refresh]
  );

  return (
    <FeatureContext.Provider value={value}>{children}</FeatureContext.Provider>
  );
}

export function useFeatureContext(): FeatureState {
  const value = useContext(FeatureContext);
  if (!value) {
    throw new Error("useFeatureContext must be used inside FeatureProvider");
  }
  return value;
}
