// ============================================================
// MenuContext.tsx
// ------------------------------------------------------------
// Session-wide cache of the resolved menu for the current user.
//
// The backend is the source of truth. This context:
//   * loads /api/menu/me once on mount
//   * exposes the resolved items + role to any component
//   * exposes refresh() so /settings/permissions can invalidate
//     the cache after a save without a full page reload
//
// Nothing in here decides visibility. It only caches what the
// backend already decided.
// ============================================================

"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  ReactNode,
} from "react";
import { getMyMenu, ResolvedMenuItem } from "@/lib/menuPermissions";
import { isLoggedIn } from "@/lib/api";

type MenuState = {
  items: ResolvedMenuItem[];
  role: string;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
};

const MenuContext = createContext<MenuState | null>(null);

export function MenuProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ResolvedMenuItem[]>([]);
  const [role, setRole] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    // Don't even try if not logged in — the sidebar will render
    // nothing useful anyway and this keeps the console clean.
    if (!isLoggedIn()) {
      setItems([]);
      setRole("");
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const data = await getMyMenu();
      setItems(data.items);
      setRole(data.role);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to load menu";
      setError(msg);
      // Leave items as-is; the sidebar will show whatever it had.
      // On first load that's an empty list — the Sidebar has its
      // own fallback for that case.
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <MenuContext.Provider
      value={{ items, role, loading, error, refresh: load }}
    >
      {children}
    </MenuContext.Provider>
  );
}

// ------------------------------------------------------------
// Consumer hook. Throws if used outside a MenuProvider so we
// catch the mistake at dev time instead of getting silent nulls.
// ------------------------------------------------------------
export function useMenu(): MenuState {
  const ctx = useContext(MenuContext);
  if (!ctx) {
    throw new Error("useMenu must be used inside a <MenuProvider>");
  }
  return ctx;
}