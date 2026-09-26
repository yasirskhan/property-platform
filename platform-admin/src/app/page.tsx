"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getPlatformToken } from "@/lib/platformApi";

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    router.replace(getPlatformToken() ? "/dashboard" : "/login");
  }, [router]);

  return <main className="p-8 text-sm text-slate-500">Opening platform console…</main>;
}
