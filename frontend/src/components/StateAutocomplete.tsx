"use client";

import { useEffect, useRef, useState } from "react";
import { US_STATES } from "@/lib/usStates";

type Props = {
  value: string;
  onChange: (code: string) => void;
  placeholder?: string;
};

export default function StateAutocomplete({
  value,
  onChange,
  placeholder = "Type a state...",
}: Props) {
  const [query, setQuery] = useState(value);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Sync external value changes
  useEffect(() => {
    setQuery(value);
  }, [value]);

  // Close on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const filtered = query
    ? US_STATES.filter(
        (s) =>
          s.name.toLowerCase().startsWith(query.toLowerCase()) ||
          s.code.toLowerCase() === query.toLowerCase()
      )
    : US_STATES;

  function select(code: string) {
    onChange(code);
    setQuery(code);
    setOpen(false);
  }

  return (
    <div ref={ref} className="relative">
      <input
        type="text"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        placeholder={placeholder}
        className="input"
        autoComplete="off"
      />
      {open && filtered.length > 0 && (
        <div className="absolute z-20 mt-1 w-full bg-white border border-slate-200 rounded-lg shadow-lg max-h-64 overflow-y-auto">
          {filtered.slice(0, 10).map((s) => (
            <button
              key={s.code}
              type="button"
              onClick={() => select(s.code)}
              className="w-full text-left px-4 py-2 hover:bg-slate-50 text-sm"
            >
              <span className="font-medium text-slate-900">{s.name}</span>
              <span className="text-slate-400 ml-2">({s.code})</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}