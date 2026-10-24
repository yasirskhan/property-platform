"use client";

export default function ConfirmModal({
  open, title, description, confirmLabel = "Confirm", cancelLabel = "Cancel",
  busy = false, danger = false, onConfirm, onCancel,
}: {
  open: boolean; title: string; description: string; confirmLabel?: string;
  cancelLabel?: string; busy?: boolean; danger?: boolean;
  onConfirm: () => void | Promise<void>; onCancel: () => void;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" role="presentation"
      onMouseDown={(event) => { if (event.target === event.currentTarget && !busy) onCancel(); }}>
      <div role="dialog" aria-modal="true" aria-labelledby="confirm-modal-title" className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
        <h2 id="confirm-modal-title" className="text-lg font-semibold text-slate-900">{title}</h2>
        <p className="mt-2 text-sm text-slate-600">{description}</p>
        <div className="mt-6 flex justify-end gap-3">
          <button type="button" disabled={busy} onClick={onCancel} className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50">{cancelLabel}</button>
          <button type="button" disabled={busy} onClick={() => void onConfirm()}
            className={danger ? "rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50" : "rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"}>
            {busy ? "Working..." : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
