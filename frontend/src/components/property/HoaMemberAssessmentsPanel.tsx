"use client";
import { useEffect, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";
import HoaMemberPaymentsPanel from "@/components/property/HoaMemberPaymentsPanel";

type Board = { id: number; decision: "APPROVED"|"DENIED"; member_user_id: number|null; approved_amount: string|null; decided_on: string };
type Who = { contact_link_id: number; contact_name: string };
type Member = { id: number; email: string; first_name: string; last_name: string; is_verified: boolean; is_active: boolean };
type Account = { id: number; number: string; name: string; account_type: "ASSET"|"INCOME" };
type Period = { id: number; proposed_on: string; proposed_amount: string; status: string };
type Charge = { id: number; occurrence_id: number; member_user_id: number; amount: string; amount_paid: string; due_on: string; status: "OPEN"|"PAID"|"REVERSED"; gl_transaction_id: number; reversal_transaction_id: number|null };

export default function HoaMemberAssessmentsPanel({ associationId, propertyId, proposalId, proposalAmount, canEdit }:
  {associationId:number;propertyId:number;proposalId:number;proposalAmount:string;canEdit:boolean}) {
  const base="/api/hoa/associations/"+associationId+"/draft-assessments/"+proposalId;
  const query="?property_id="+propertyId;
  const [board,setBoard]=useState<Board|null>(null);
  const [payer,setPayer]=useState<Who|null>(null);
  const [members,setMembers]=useState<Member[]>([]);
  const [accounts,setAccounts]=useState<Account[]>([]);
  const [periods,setPeriods]=useState<Period[]>([]);
  const [charges,setCharges]=useState<Charge[]>([]);
  const [choice,setChoice]=useState<"APPROVED"|"DENIED">("APPROVED");
  const [memberId,setMemberId]=useState("");
  const [note,setNote]=useState("");
  const [dueOn,setDueOn]=useState("");
  const [arId,setArId]=useState("");
  const [incomeId,setIncomeId]=useState("");
  const [reverseOn,setReverseOn]=useState("");
  const [reason,setReason]=useState("");
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [message,setMessage]=useState("");
  async function reload() {
    const [decision,ledger,plan] = await Promise.all([
      apiGet(base+"/board-decision"+query) as Promise<Board|null>,
      apiGet(base+"/member-ledger"+query) as Promise<Charge[]>,
      apiGet(base+"/planned-occurrences"+query) as Promise<Period[]>,
    ]);
    setBoard(decision);setCharges(ledger);setPeriods(plan);
  }
  useEffect(()=>{
    let active=true;
    void Promise.all([
      apiGet(base+"/board-decision"+query) as Promise<Board|null>,
      apiGet(base+"/member-ledger"+query) as Promise<Charge[]>,
      apiGet(base+"/planned-occurrences"+query) as Promise<Period[]>,
      apiGet(base+"/payer-draft"+query) as Promise<Who|null>,
      apiGet("/api/hoa/associations/"+associationId+"/arc-fee-gl-options"+query) as Promise<Account[]>,
      apiGet("/users") as Promise<Member[]>,
    ]).then(([decision,ledger,plan,who,gl,users])=>{
      if(!active)return;
      setBoard(decision);setCharges(ledger);setPeriods(plan);setPayer(who);
      setAccounts(gl);setMembers(users.filter(u=>u.is_active&&u.is_verified));
    }).catch((cause)=>{if(active)setError(cause instanceof Error?cause.message:"Member ledger unavailable.");});
    return ()=>{active=false;};
  },[base,query,associationId]);
  async function act(action:()=>Promise<unknown>,success:string) {
    setBusy(true);setError("");setMessage("");
    try {await action();await reload();setMessage(success);}
    catch(cause){setError(cause instanceof Error?cause.message:"HOA action failed.");await reload().catch(()=>{});}
    finally{setBusy(false);}
  }
  function decide(){
    if(!canEdit||busy||!note.trim()||(choice==="APPROVED"&&(!payer||!memberId)))return;
    if(!window.confirm("Record this association board decision? Final decisions cannot be edited."))return;
    void act(()=>apiPost(base+"/board-decision",{
      property_id:propertyId,decision:choice,decision_note:note.trim(),
      contact_link_id:choice==="APPROVED"?payer?.contact_link_id:null,
      member_user_id:choice==="APPROVED"?Number(memberId):null,
    }),"Board decision recorded. No money posted by the decision.");
  }
  function issue(period:Period) {
    if(!board||board.decision!=="APPROVED"||busy||!dueOn||!arId||!incomeId)return;
    if(!window.confirm("Post an actual HOA member receivable to the central GL?"))return;
    void act(()=>apiPost(base+"/planned-occurrences/"+period.id+"/issue",{
      property_id:propertyId,member_user_id:board.member_user_id,
      due_on:dueOn,receivable_gl_account_id:Number(arId),income_gl_account_id:Number(incomeId),
    }),"Approved member receivable posted. No tenant charge inferred.");
  }
  function reverse(charge:Charge){
    if(busy||!reverseOn||!reason.trim())return;
    if(!window.confirm("Post an immutable GL reversal for this HOA receivable?"))return;
    void act(()=>apiPost(base+"/member-ledger/"+charge.id+"/reverse",{
      property_id:propertyId,reversal_on:reverseOn,reason:reason.trim(),
    }),"Member assessment reversed by a new central GL entry.");
  }
  return <section className="w-full space-y-3 rounded border border-teal-200 bg-teal-50 p-3 text-xs">
    <h4 className="font-semibold">Board-approved member assessments</h4>
    <p>An association-authorized board login records the decision. An accountant separately
      issues each period to its verified member through the existing balanced GL. This is
      a member receivable, not a tenant Charge. A draft contact alone is not a debtor.</p>
    {error&&<p role="alert" className="text-red-700">{error}</p>}
    {message&&<p role="status" className="text-green-800">{message}</p>}
    {board&&<p role="status" className="font-semibold">Board decision: {board.decision} on {board.decided_on}
      {board.decision==="APPROVED"?" · Approved $"+board.approved_amount+" · Member #"+board.member_user_id:""}</p>}
    {canEdit&&!board&&<div className="space-y-2 border-t pt-2">
      <h5 className="font-medium">Record board decision for proposed {"$"+proposalAmount}</h5>
      <label className="block">Board decision
        <select aria-label="Assessment board decision" value={choice}
          onChange={e=>setChoice(e.target.value as "APPROVED"|"DENIED")}
          className="mt-1 block rounded border p-2">
          <option value="APPROVED">APPROVED</option><option value="DENIED">DENIED</option>
        </select>
      </label>
      {choice==="APPROVED"&&<>
        <p>Suggested contact: {payer?.contact_name||"none"}. Select the corresponding verified member account.</p>
        <label className="block">Responsible verified member
          <select aria-label="Assessment responsible member" value={memberId}
            onChange={e=>setMemberId(e.target.value)} className="mt-1 block w-full rounded border p-2">
            <option value="">Choose member</option>
            {members.map(m=><option key={m.id} value={m.id}>{m.first_name} {m.last_name} · {m.email}</option>)}
          </select>
        </label>
      </>}
      <label className="block">Board decision note
        <textarea maxLength={1500} value={note} onChange={e=>setNote(e.target.value)}
          className="mt-1 block w-full rounded border p-2"/>
      </label>
      <button type="button" disabled={busy||!note.trim()||(choice==="APPROVED"&&(!payer||!memberId))}
        onClick={decide} className="rounded bg-teal-900 px-3 py-2 text-white disabled:opacity-50">
        Record association board decision</button>
    </div>}
    {board?.decision==="APPROVED"&&canEdit&&<div className="space-y-2 border-t pt-2">
      <h5 className="font-semibold">Issue approved member receivable</h5>
      <label className="block">Assessment due date<input type="date" value={dueOn}
        onChange={e=>setDueOn(e.target.value)} className="mt-1 block rounded border p-2"/></label>
      <label className="block">Member receivable GL
        <select aria-label="Assessment receivable GL" value={arId} onChange={e=>setArId(e.target.value)}
          className="mt-1 block w-full rounded border p-2">
          <option value="">Select asset GL</option>
          {accounts.filter(x=>x.account_type==="ASSET").map(x=><option key={x.id} value={x.id}>{x.number} · {x.name}</option>)}
        </select>
      </label>
      <label className="block">Assessment income GL
        <select aria-label="Assessment income GL" value={incomeId} onChange={e=>setIncomeId(e.target.value)}
          className="mt-1 block w-full rounded border p-2">
          <option value="">Select income GL</option>
          {accounts.filter(x=>x.account_type==="INCOME").map(x=><option key={x.id} value={x.id}>{x.number} · {x.name}</option>)}
        </select>
      </label>
      <ol className="space-y-1">{periods.filter(x=>x.status==="PLANNED").map(p=><li key={p.id}>
        {p.proposed_on} · {"$"+p.proposed_amount}{" "}
        {charges.some(x=>x.occurrence_id===p.id)?"Issued":
          <button type="button" disabled={busy||!dueOn||!arId||!incomeId}
            onClick={()=>issue(p)} className="text-blue-700 disabled:opacity-50">Issue member receivable</button>}
      </li>)}</ol>
    </div>}
    <div className="space-y-2 border-t pt-2"><h5 className="font-semibold">Member assessment ledger</h5>
      {charges.length===0&&<p>No posted member assessments.</p>}
      {charges.map(c=><div key={c.id} className="rounded border bg-white p-2">
        <p className="font-medium">Assessment #{c.id} · Member #{c.member_user_id} · {"$"+c.amount}
          {" · "}Due {c.due_on} · {c.status}</p>
        <p>Paid {"$"+c.amount_paid} · Original GL #{c.gl_transaction_id}
          {c.reversal_transaction_id?" · Reversal GL #"+c.reversal_transaction_id:""}</p>
        {canEdit&&c.status==="OPEN"&&Number(c.amount_paid)===0&&<div className="space-y-1">
          <label className="block">Reversal date<input type="date" value={reverseOn}
            onChange={e=>setReverseOn(e.target.value)} className="mt-1 block rounded border p-2"/></label>
          <label className="block">Reversal reason<textarea maxLength={500} value={reason}
            onChange={e=>setReason(e.target.value)} className="mt-1 block w-full rounded border p-2"/></label>
          <button type="button" disabled={busy||!reverseOn||!reason.trim()} onClick={()=>reverse(c)}
            className="text-red-700 disabled:opacity-50">Reverse member assessment via GL</button>
        </div>}
        {c.status!=="REVERSED"&&<HoaMemberPaymentsPanel
          associationId={associationId} propertyId={propertyId}
          proposalId={proposalId} chargeId={c.id} memberId={c.member_user_id}
          amount={c.amount} amountPaid={c.amount_paid} status={c.status}
          canEdit={canEdit} onChange={()=>{void reload();}} />}
      </div>)}
    </div>
  </section>;
}
