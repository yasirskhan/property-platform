"use client";

import { useFeatureContext } from "@/contexts/FeatureContext";

export function useFlag(key: string): boolean {
  const { flags } = useFeatureContext();
  return flags[key] === true;
}
