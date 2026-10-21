"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiGet, apiPost, apiPut } from "@/lib/api";

type Rule = {
  urgency: string; daypart: string; configured: boolean;
  first_target: string; backup_target: string; timeout_minutes: number; escalate: boolean;
  primary_contact_user_id: number | null; backup_contact_user_id: number | null;
};
type Group = {
  id: number; name: string; is_default: boolean; timezone_name: string;
  business_start_hour: number; business_end_hour: number;
  property_ids: number[]; automation_requested: boolean; rules: Rule[];
};
type Choice = { id: number; name: string };
const urgencies = ["emergency", "normal", "low"] as const;
const dayparts = ["business_hours", "after_hours"] as const;

export default function MaintenanceDispatchSettingsPage() {
  const [viewerRole, setViewerRole] = useState("");
  const [groups, setGroups] = useState<Group[] | null>(null);
  const [properties, setProperties] = useState<Choice[]>([]);
  const [contacts, setContacts] = useState<Choice[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [newName, setNewName] = useState("");
  const [name, setName] = useState("");
  const [timezone, setTimezone] = useState("UTC");
  const [startHour, setStartHour] = useState(9);
  const [endHour, setEndHour] = useState(17);
  const [automationRequested, setAutomationRequested] = useState(false);
  const [selectedProperties, setSelectedProperties] = useState<number[]>([]);
  const [urgency, setUrgency] = useState<string>("emergency");
  const [daypart, setDaypart] = useState<string>("after_hours");
  const [firstTarget, setFirstTarget] = useState("crew");
  const [backupTarget, setBackupTarget] = useState("vendor");
  const [timeoutMinutes, setTimeoutMinutes] = useState(15);
  const [escalate, setEscalate] = useState(false);
  const [primaryContact, setPrimaryContact] = useState("");
  const [backupContact, setBackupContact] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const chosen = groups?.find((item) => item.id === selectedId) || null;
  const savedRule = chosen?.rules.find((r) => r.urgency === urgency && r.daypart === daypart);

  const refresh = useCallback(async () => {
    const rows = await apiGet("/api/maintenance/dispatch-groups") as Group[];
    if (!Array.isArray(rows) || !rows.some((item) => item.is_default))
      throw new Error("Dispatch group configuration unavailable.");
    setGroups(rows);
    setSelectedId((current) => current && rows.some((g) => g.id === current)
      ? current : rows.find((g) => g.is_default)?.id || null);
  }, []);

  useEffect(() => {
    let active = true;
    apiGet("/auth/me").then((user: {role: string}) => {
      if (!active) return;
      const role = String(user.role).toUpperCase();
      setViewerRole(role);
      if (!["ADMIN", "OWNER"].includes(role)) return;
      Promise.all([
        apiGet("/api/maintenance/dispatch-groups") as Promise<Group[]>,
        apiGet("/api/maintenance/dispatch-groups/properties") as Promise<Choice[]>,
        apiGet("/api/maintenance/dispatch-groups/contacts") as Promise<Choice[]>,
      ]).then(([items, props, staff]) => {
        if (!active) return;
        if (!Array.isArray(items) || !Array.isArray(props) || !Array.isArray(staff)
            || !items.some((g) => g.is_default)) throw new Error("Dispatch configuration unavailable.");
        setGroups(items); setProperties(props); setContacts(staff);
        setSelectedId(items.find((g) => g.is_default)?.id || null);
      }).catch((cause) => { if (active) setError(cause instanceof Error ? cause.message : "Could not load dispatch settings."); });
    }).catch(() => { if (active) setViewerRole("DENIED"); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!chosen) return;
    setName(chosen.name); setTimezone(chosen.timezone_name);
    setStartHour(chosen.business_start_hour); setEndHour(chosen.business_end_hour);
    setAutomationRequested(Boolean(chosen.automation_requested));
    setSelectedProperties(chosen.is_default ? [] : chosen.property_ids);
  }, [chosen?.id, groups]);

  useEffect(() => {
    if (!savedRule) return;
    setFirstTarget(savedRule.first_target);
    setBackupTarget(savedRule.backup_target);
    setTimeoutMinutes(savedRule.timeout_minutes);
    setEscalate(savedRule.escalate);
    setPrimaryContact(savedRule.primary_contact_user_id ? String(savedRule.primary_contact_user_id) : "");
    setBackupContact(savedRule.backup_contact_user_id ? String(savedRule.backup_contact_user_id) : "");
  }, [selectedId, urgency, daypart, groups]);

  async function createGroup() {
    if (saving || !newName.trim() || newName.trim().toLowerCase() === "default") return;
    setSaving(true); setError(""); setNotice("");
    try {
      const result = await apiPost("/api/maintenance/dispatch-groups", {
        name: newName.trim(), timezone_name: "UTC",
        business_start_hour: 9, business_end_hour: 17, property_ids: [],
        automation_requested: false,
      }) as Group;
      if (!result?.id || result.is_default) throw new Error("Invalid group response.");
      setNewName(""); await refresh(); setSelectedId(result.id);
      setNotice("Maintenance group created. Set a property assignment and dispatch policies next.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to create group."); }
    finally { setSaving(false); }
  }

  async function saveGroup() {
    if (!chosen || saving) return;
    if (startHour < 0 || endHour > 24 || startHour >= endHour) {
      setError("Business-hour start must be earlier than end."); return;
    }
    setSaving(true); setError(""); setNotice("");
    try {
      const result = await apiPut("/api/maintenance/dispatch-groups/" + chosen.id, {
        name: chosen.is_default ? "DEFAULT" : name.trim(),
        timezone_name: timezone.trim(), business_start_hour: startHour,
        business_end_hour: endHour, property_ids: chosen.is_default ? [] : selectedProperties,
        automation_requested: automationRequested,
      }) as Group;
      if (result.id !== chosen.id) throw new Error("Invalid saved group response.");
      await refresh(); setNotice("Maintenance group settings and property membership saved.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to save group."); }
    finally { setSaving(false); }
  }

  async function saveRule() {
    if (!chosen || saving) return;
    setSaving(true); setError(""); setNotice("");
    try {
      const result = await apiPut(
        "/api/maintenance/dispatch-groups/" + chosen.id + "/rules/" + urgency + "/" + daypart, {
          first_target: firstTarget, backup_target: backupTarget,
          timeout_minutes: timeoutMinutes, escalate,
          primary_contact_user_id: primaryContact ? Number(primaryContact) : null,
          backup_contact_user_id: backupContact ? Number(backupContact) : null,
        }) as Rule;
      if (!result.configured || result.urgency !== urgency || result.daypart !== daypart)
        throw new Error("Unexpected dispatch rule response.");
      await refresh();
      setNotice("Dispatch policy saved for planning. No crew/vendor was contacted and no timeout is running.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to save policy."); }
    finally { setSaving(false); }
  }

  if (viewerRole && !["ADMIN", "OWNER"].includes(viewerRole)) {
    return <p className="rounded-lg border p-5" role="alert">Only Owner/Admin can configure maintenance dispatch groups.</p>;
  }

  return <div className="space-y-6">
    <header className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-2xl font-bold">Maintenance dispatch settings</h1>
        <p className="mt-2 text-sm text-slate-600">
          Organize properties into one effective maintenance group, set business hours and configure
          emergency, normal and low-urgency rules. These are settings only. Automatic calls, messages,
          escalation and vendor payments are not active.
        </p>
      </div>
      <Link href="/dashboard/maintenance/on-call" className="rounded-lg border px-3 py-2 text-sm">On-call calendar</Link>
    </header>
    {error && <p role="alert" className="rounded border border-red-300 p-3 text-sm text-red-800">{error}</p>}
    {notice && <p role="status" className="rounded border p-3 text-sm">{notice}</p>}
    {!groups ? <p className="text-sm text-slate-600">Loading authorized dispatch configuration...</p> : <>
      <section className="rounded-xl border bg-white p-5" aria-label="Maintenance dispatch groups">
        <h2 className="font-semibold">Groups and property coverage</h2>
        <p className="mt-1 text-xs text-slate-600">
          Unassigned properties inherit DEFAULT. Moving a property replaces its other nondefault group binding.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <input aria-label="New maintenance group name" className="w-full max-w-sm rounded border p-2 text-sm"
            value={newName} onChange={(e) => setNewName(e.target.value)} maxLength={100}
            placeholder="New group name" disabled={saving}/>
          <button type="button" className="rounded bg-slate-900 px-3 py-2 text-sm text-white disabled:opacity-50"
            disabled={saving || !newName.trim()} onClick={() => void createGroup()}>Create group</button>
        </div>
        <label className="mt-4 block text-sm">Choose a group
          <select aria-label="Dispatch settings group" className="mt-1 block w-full max-w-lg rounded border p-2"
            value={selectedId ?? ""} onChange={(e) => setSelectedId(Number(e.target.value))} disabled={saving}>
            {groups.map((group) => <option key={group.id} value={group.id}>
              {group.name} ({group.property_ids.length} active properties)
            </option>)}
          </select>
        </label>
        {chosen && <div className="mt-4 space-y-3">
          <div className="grid gap-3 md:grid-cols-4">
            <label className="text-sm">Name
              <input aria-label="Dispatch group name" className="mt-1 block w-full rounded border p-2"
                value={name} onChange={(e) => setName(e.target.value)} maxLength={100}
                disabled={saving || chosen.is_default}/>
            </label>
            <label className="text-sm">IANA timezone
              <input aria-label="Dispatch business timezone" className="mt-1 block w-full rounded border p-2"
                value={timezone} onChange={(e) => setTimezone(e.target.value)} maxLength={64} disabled={saving}
                placeholder="America/New_York"/>
            </label>
            <label className="text-sm">Business start hour (0-23)
              <input aria-label="Dispatch business start hour" type="number" min={0} max={23}
                className="mt-1 block w-full rounded border p-2" value={startHour}
                onChange={(e) => setStartHour(Number(e.target.value))} disabled={saving}/>
            </label>
            <label className="text-sm">Business end hour (1-24)
              <input aria-label="Dispatch business end hour" type="number" min={1} max={24}
                className="mt-1 block w-full rounded border p-2" value={endHour}
                onChange={(e) => setEndHour(Number(e.target.value))} disabled={saving}/>
            </label>
          </div>
          <fieldset className="rounded border p-3">
            <legend className="text-sm font-medium">Property membership</legend>
            {chosen.is_default ? <p className="text-xs text-slate-600">
              DEFAULT includes all {chosen.property_ids.length} properties without a named override.
              Remove properties from a named group to return them here.
            </p> : <div className="grid gap-2 sm:grid-cols-2">
              {properties.map((p) => <label key={p.id} className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={selectedProperties.includes(p.id)} disabled={saving}
                  onChange={(e) => setSelectedProperties((current) =>
                    e.target.checked ? [...current, p.id] : current.filter((id) => id !== p.id))}/>
                {p.name}
              </label>)}
            </div>}
          </fieldset>
          <label className="flex items-start gap-2 rounded border p-3 text-sm">
            <input aria-label="Request future automated dispatch" type="checkbox" checked={automationRequested}
              onChange={(e) => setAutomationRequested(e.target.checked)} disabled={saving}/>
            <span>Request automated dispatch for this group. This only records Owner/Admin intent; automatic execution,
              delivery and escalation remain disabled until the separately verified executor is released.</span>
          </label>
          <button type="button" disabled={saving} onClick={() => void saveGroup()}
            className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">Save group settings</button>
        </div>}
      </section>
      {chosen && <section className="rounded-xl border bg-white p-5" aria-label="Dispatch urgency and after-hours policies">
        <h2 className="font-semibold">Urgency and time-of-day policy</h2>
        <p className="mt-1 text-xs text-slate-600">
          Six independent policy slots per group. Configured rules are stored for future dispatch execution;
          no automatic escalation or external notification service is enabled yet.
        </p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <label className="text-sm">Urgency
            <select aria-label="Dispatch policy urgency" className="mt-1 block w-full rounded border p-2"
              value={urgency} onChange={(e) => setUrgency(e.target.value)} disabled={saving}>
              {urgencies.map((u) => <option value={u} key={u}>{u}</option>)}
            </select>
          </label>
          <label className="text-sm">Time of day
            <select aria-label="Dispatch policy daypart" className="mt-1 block w-full rounded border p-2"
              value={daypart} onChange={(e) => setDaypart(e.target.value)} disabled={saving}>
              {dayparts.map((d) => <option value={d} key={d}>{d.replaceAll("_", " ")}</option>)}
            </select>
          </label>
        </div>
        <p className="mt-3 text-sm">{savedRule?.configured ? "Configured policy" : "Unconfigured preview. Save to record a policy."}</p>
        <div className="mt-3 grid gap-3 md:grid-cols-3">
          <label className="text-sm">Primary target
            <select aria-label="Dispatch policy primary target" className="mt-1 block w-full rounded border p-2"
              value={firstTarget} onChange={(e) => setFirstTarget(e.target.value)} disabled={saving}>
              <option value="crew">On-call crew</option><option value="vendor">Preferred vendor</option><option value="manager">Management</option>
            </select>
          </label>
          <label className="text-sm">Backup target
            <select aria-label="Dispatch policy backup target" className="mt-1 block w-full rounded border p-2"
              value={backupTarget} onChange={(e) => setBackupTarget(e.target.value)} disabled={saving}>
              <option value="vendor">Preferred vendor</option><option value="manager">Management</option>
            </select>
          </label>
          <label className="text-sm">Escalation timeout (minutes)
            <input aria-label="Dispatch policy timeout" type="number" min={1} max={1440}
              value={timeoutMinutes} onChange={(e) => setTimeoutMinutes(Number(e.target.value))}
              disabled={saving} className="mt-1 block w-full rounded border p-2"/>
          </label>
          <label className="text-sm">Primary contact (Owner/Admin)
            <select aria-label="Dispatch primary contact" value={primaryContact}
              onChange={(e) => setPrimaryContact(e.target.value)} disabled={saving}
              className="mt-1 block w-full rounded border p-2">
              <option value="">Not configured</option>
              {contacts.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </label>
          <label className="text-sm">Backup contact (Owner/Admin)
            <select aria-label="Dispatch backup contact" value={backupContact}
              onChange={(e) => setBackupContact(e.target.value)} disabled={saving}
              className="mt-1 block w-full rounded border p-2">
              <option value="">Not configured</option>
              {contacts.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={escalate} disabled={saving} onChange={(e) => setEscalate(e.target.checked)}/>
            Enable escalation in policy (executor not active)
          </label>
        </div>
        <button type="button" className="mt-3 rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50"
          disabled={saving || timeoutMinutes < 1 || timeoutMinutes > 1440}
          onClick={() => void saveRule()}>Save dispatch policy</button>
        <p className="mt-2 text-xs text-slate-600">
          Crew shifts, preferred vendors, provider delivery confirmation, real timers and manual recovery
          require separate operational verification. Settings are not notifications.
        </p>
      </section>}
    </>}
  </div>;
}
