"use client";

import { useEffect, useRef, useState } from "react";

export type AddressSuggestion = {
  address_line1: string;
  city: string;
  state: string;
  zip_code: string;
  formatted: string;
};

type Props = {
  onSelect: (address: AddressSuggestion) => void;
  initialValue?: string;
  placeholder?: string;
};

export default function AddressAutocomplete({
  onSelect,
  initialValue = "",
  placeholder = "Start typing an address...",
}: Props) {
  const [query, setQuery] = useState(initialValue);
  const [suggestions, setSuggestions] = useState<AddressSuggestion[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setQuery(initialValue);
  }, [initialValue]);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);

    if (query.length < 5) {
      setSuggestions([]);
      return;
    }

    debounceRef.current = setTimeout(async () => {
      const key = process.env.NEXT_PUBLIC_GEOAPIFY_KEY;
      if (!key) {
        console.warn("Missing NEXT_PUBLIC_GEOAPIFY_KEY in .env.local");
        return;
      }

      setLoading(true);
      try {
        const url = `https://api.geoapify.com/v1/geocode/autocomplete?text=${encodeURIComponent(
          query
        )}&filter=countrycode:us&format=json&limit=8&apiKey=${key}`;
        const res = await fetch(url);
        const data = await res.json();

        const results: AddressSuggestion[] = (data.results || []).map(
          (r: {
            housenumber?: string;
            street?: string;
            address_line1?: string;
            city?: string;
            state?: string;
            postcode?: string;
            formatted?: string;
          }) => ({
            address_line1:
              r.address_line1 ||
              [r.housenumber, r.street].filter(Boolean).join(" ") ||
              "",
            city: r.city || "",
            state: r.state || "",
            zip_code: r.postcode || "",
            formatted: r.formatted || "",
          })
        );

        setSuggestions(results);
        setOpen(true);
      } catch (err) {
        console.error("Address lookup failed", err);
      } finally {
        setLoading(false);
      }
    }, 350);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query]);

  function select(s: AddressSuggestion) {
    onSelect(s);
    setQuery(s.formatted || s.address_line1);
    setOpen(false);
    setSuggestions([]);
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
      {loading && <p className="text-xs text-slate-400 mt-1">Searching…</p>}
      {open && suggestions.length > 0 && (
        <div className="absolute z-30 mt-1 w-full bg-white border border-slate-200 rounded-lg shadow-lg max-h-72 overflow-y-auto">
          {suggestions.map((s, i) => (
            <button
              key={i}
              type="button"
              onClick={() => select(s)}
              className="w-full text-left px-4 py-2 hover:bg-slate-50 text-sm border-b border-slate-100 last:border-0"
            >
              <span className="font-medium text-slate-900">
                {s.address_line1}
              </span>
              <span className="block text-xs text-slate-500">
                {s.city}, {s.state} {s.zip_code}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}