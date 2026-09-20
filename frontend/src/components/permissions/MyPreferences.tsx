// ============================================================
// MyPreferences.tsx
// ------------------------------------------------------------
// The My Preferences tab in Settings -> Permissions.
//
// Layer 4 of the menu system: personal order + personal hides.
// These affect only the current user. They can only subtract
// visibility — an item the role hides cannot be un-hidden here.
//
// Features:
//   * Drag to reorder (per-user)
//   * Toggle hide/show (per-user)
//   * Auto-saves on every change
//
// Only shows items the user can currently see. Items the role
// denies are not listed at all (they can't be recovered here).
// ============================================================

"use client";

import { useEffect, useState } from "react";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import {
  GripVertical,
  Eye,
  EyeOff,
  RotateCcw,
  Loader2,
  Check,
} from "lucide-react";
import { useMenu } from "@/contexts/MenuContext";
import {
  getMyPreferences,
  updateMyPreferences,
} from "@/lib/menuPermissions";
import { getMenuEntry } from "@/lib/menuConfig";

type Props = {
  onSaved: () => void;
};

// ------------------------------------------------------------
// Sortable row
// ------------------------------------------------------------
function SortableRow({
  menuKey,
  label,
  hidden,
  isChild,
  onToggle,
}: {
  menuKey: string;
  label: string;
  hidden: boolean;
  isChild: boolean;
  onToggle: (key: string) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: menuKey });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`flex items-center gap-3 px-3 py-2 bg-white border border-slate-200 rounded mb-1.5 ${
        isChild ? "ml-6" : ""
      }`}
    >
      <button
        {...attributes}
        {...listeners}
        className="cursor-grab active:cursor-grabbing text-slate-400 hover:text-slate-700"
        title="Drag to reorder"
      >
        <GripVertical className="w-4 h-4" />
      </button>

      <span
        className={`flex-1 text-sm ${
          hidden ? "text-slate-400 line-through" : "text-slate-800"
        }`}
      >
        {label}
      </span>

      <button
        onClick={() => onToggle(menuKey)}
        className="p-1.5 rounded hover:bg-slate-100"
        title={hidden ? "Show in my sidebar" : "Hide from my sidebar"}
      >
        {hidden ? (
          <EyeOff className="w-4 h-4 text-slate-400" />
        ) : (
          <Eye className="w-4 h-4 text-slate-600" />
        )}
      </button>
    </div>
  );
}

// ------------------------------------------------------------
// Main component
// ------------------------------------------------------------
export default function MyPreferences({ onSaved }: Props) {
  // Pull the resolved menu — this is what the user currently sees.
  // We use it as the "available" set for personal customization.
  const { items, loading: menuLoading, refresh } = useMenu();

  const [order, setOrder] = useState<string[]>([]);
  const [hidden, setHidden] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ----------------------------------------------------------
  // Load current personal preferences on mount
  // ----------------------------------------------------------
  useEffect(() => {
    getMyPreferences()
      .then((p) => {
        setOrder(p.order);
        setHidden(p.hidden);
      })
      .catch((e) =>
        setError(e instanceof Error ? e.message : "Failed to load")
      )
      .finally(() => setLoading(false));
  }, []);

  // ----------------------------------------------------------
  // The canonical key list: what the user currently sees.
  // We preserve the loaded order but only for keys that still
  // exist in the resolved menu; anything new is appended.
  // ----------------------------------------------------------
  const availableKeys = items.map((i) => i.key);
  const keySet = new Set(availableKeys);

  const orderedKeys: string[] = [];
  const seen = new Set<string>();
  for (const k of order) {
    if (keySet.has(k) && !seen.has(k)) {
      orderedKeys.push(k);
      seen.add(k);
    }
  }
  for (const k of availableKeys) {
    if (!seen.has(k)) {
      orderedKeys.push(k);
      seen.add(k);
    }
  }

  // ----------------------------------------------------------
  // Drag end
  // ----------------------------------------------------------
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  async function persist(nextOrder: string[], nextHidden: string[]) {
    setSaving(true);
    setError(null);
    try {
      await updateMyPreferences(nextOrder, nextHidden);
      setSavedFlash(true);
      window.setTimeout(() => setSavedFlash(false), 1200);
      // Ask the shared menu context to re-fetch so the sidebar
      // reflects the change immediately.
      await refresh();
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  async function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIdx = orderedKeys.indexOf(active.id as string);
    const newIdx = orderedKeys.indexOf(over.id as string);
    if (oldIdx < 0 || newIdx < 0) return;
    const next = arrayMove(orderedKeys, oldIdx, newIdx);
    setOrder(next);
    await persist(next, hidden);
  }

  async function toggleHidden(key: string) {
    const next = hidden.includes(key)
      ? hidden.filter((k) => k !== key)
      : [...hidden, key];
    setHidden(next);
    await persist(order, next);
  }

  async function resetToDefault() {
    const ok = window.confirm(
      "Reset your personal preferences? Order and hide selections will be cleared."
    );
    if (!ok) return;
    setOrder([]);
    setHidden([]);
    await persist([], []);
  }

  // ----------------------------------------------------------
  // Render
  // ----------------------------------------------------------
  if (loading || menuLoading) {
    return <div className="p-4 text-slate-500">Loading…</div>;
  }

  if (orderedKeys.length === 0) {
    return (
      <div className="p-4 bg-slate-50 border border-slate-200 rounded text-slate-500 text-sm">
        There are no menu items to customize for your role.
      </div>
    );
  }

  return (
    <div className="max-w-2xl">
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded">
          {error}
        </div>
      )}

      <div className="mb-4 text-sm text-slate-600">
        Drag to reorder. Click the eye icon to hide an item from your
        own sidebar. These settings affect only your account.
      </div>

      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <SortableContext items={orderedKeys} strategy={verticalListSortingStrategy}>
          {orderedKeys.map((k) => {
            const entry = getMenuEntry(k);
            if (!entry) return null;
            const isChild = items.find((i) => i.key === k)?.parent !== null;
            return (
              <SortableRow
                key={k}
                menuKey={k}
                label={entry.label}
                hidden={hidden.includes(k)}
                isChild={!!isChild}
                onToggle={toggleHidden}
              />
            );
          })}
        </SortableContext>
      </DndContext>

      <div className="flex items-center gap-3 mt-5">
        <button
          onClick={resetToDefault}
          disabled={saving}
          className="inline-flex items-center gap-2 px-4 py-2 text-sm text-slate-600 hover:text-slate-900 disabled:opacity-50"
        >
          <RotateCcw className="w-4 h-4" />
          Reset to default
        </button>

        {saving && (
          <span className="inline-flex items-center gap-1 text-sm text-slate-500">
            <Loader2 className="w-4 h-4 animate-spin" />
            Saving…
          </span>
        )}

        {savedFlash && !saving && (
          <span className="inline-flex items-center gap-1 text-sm text-green-600">
            <Check className="w-4 h-4" />
            Saved
          </span>
        )}
      </div>
    </div>
  );
}