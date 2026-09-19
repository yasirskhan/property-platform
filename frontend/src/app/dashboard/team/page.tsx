"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiGet, fileUrl } from "@/lib/api";

type User = {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  phone: string | null;
  role: string;
  is_active: boolean;
  profile_photo_url: string | null;
};

type Me = { role: string };

const ROLE_LABELS: Record<string, string> = {
  admin: "Admin",
  owner: "Owner",
  manager: "Manager",
  crew: "Crew",
  tenant: "Tenant",
};

export default function TeamPage() {
  const [me, setMe] = useState<Me | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [filter, setFilter] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const meData = await apiGet("/auth/me");
        setMe(meData);

        if (meData.role === "crew" || meData.role === "tenant") {
          setError("You don't have access to team management.");
          setLoading(false);
          return;
        }

        const data = await apiGet("/users");
        setUsers(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Load failed");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) return <div className="text-slate-500">Loading…</div>;
  if (error) return <div className="text-red-600">{error}</div>;

  const canCreate =
    me?.role === "admin" || me?.role === "owner" || me?.role === "manager";

  const filtered = filter ? users.filter((u) => u.role === filter) : users;

  const counts = users.reduce<Record<string, number>>((acc, u) => {
    acc[u.role] = (acc[u.role] || 0) + 1;
    return acc;
  }, {});

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Team</h1>
          <p className="text-slate-500 mt-1">
            {users.length} {users.length === 1 ? "person" : "people"}
          </p>
        </div>
        {canCreate && (
          <Link
            href="/dashboard/team/new"
            className="text-sm px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-700"
          >
            + Add Person
          </Link>
        )}
      </div>

      {/* Filters */}
      <div className="flex gap-2 mb-6 flex-wrap">
        <FilterButton active={filter === ""} onClick={() => setFilter("")}>
          All ({users.length})
        </FilterButton>
        {Object.entries(ROLE_LABELS).map(([role, label]) => {
          const count = counts[role] || 0;
          if (count === 0 && filter !== role) return null;
          return (
            <FilterButton
              key={role}
              active={filter === role}
              onClick={() => setFilter(role)}
            >
              {label} ({count})
            </FilterButton>
          );
        })}
      </div>

      {/* Table */}
      {filtered.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
          <p className="text-slate-500 mb-4">No people yet.</p>
          {canCreate && (
            <Link
              href="/dashboard/team/new"
              className="inline-block px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-700 text-sm"
            >
              Add your first person
            </Link>
          )}
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <table className="w-full">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="text-left px-6 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">
                  Name
                </th>
                <th className="text-left px-6 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">
                  Email
                </th>
                <th className="text-left px-6 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">
                  Role
                </th>
                <th className="text-left px-6 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">
                  Status
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.map((u) => (
                <tr key={u.id} className="hover:bg-slate-50">
                  <td className="px-6 py-4">
                    <Link
                      href={`/dashboard/team/${u.id}`}
                      className="flex items-center gap-3"
                    >
                      {u.profile_photo_url ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={fileUrl(u.profile_photo_url)}
                          alt={u.first_name}
                          className="w-8 h-8 rounded-full object-cover border border-slate-200"
                        />
                      ) : (
                        <div className="w-8 h-8 rounded-full bg-slate-900 text-white flex items-center justify-center text-xs font-medium">
                          {u.first_name.charAt(0).toUpperCase()}
                        </div>
                      )}
                      <span className="font-medium text-slate-900">
                        {u.first_name} {u.last_name}
                      </span>
                    </Link>
                  </td>
                  <td className="px-6 py-4 text-slate-600 text-sm">{u.email}</td>
                  <td className="px-6 py-4">
                    <span className="text-xs px-2 py-1 bg-slate-100 text-slate-700 rounded-full uppercase tracking-wide">
                      {ROLE_LABELS[u.role] || u.role}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    {u.is_active ? (
                      <span className="text-xs text-green-700 bg-green-50 px-2 py-1 rounded-full">
                        Active
                      </span>
                    ) : (
                      <span className="text-xs text-red-700 bg-red-50 px-2 py-1 rounded-full">
                        Inactive
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function FilterButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`text-sm px-3 py-1.5 rounded-lg border transition ${
        active
          ? "bg-slate-900 text-white border-slate-900"
          : "bg-white text-slate-700 border-slate-200 hover:border-slate-400"
      }`}
    >
      {children}
    </button>
  );
}