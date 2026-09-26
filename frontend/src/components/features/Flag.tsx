"use client";

import type { ReactNode } from "react";

import { useFlag } from "@/hooks/useFlag";

export default function Flag({
  name,
  children,
  fallback = null,
}: {
  name: string;
  children: ReactNode;
  fallback?: ReactNode;
}) {
  return useFlag(name) ? <>{children}</> : <>{fallback}</>;
}
