"use client";
import { FormEvent, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { apiGet, apiPost } from "@/lib/api";

type Actor = {id:number;role:string};
type Vendor = {id:number;company_name:string};
type Movement = {id:number;reference:string;delta_qty:number;received_by_id:number;reason:string;reverses_id:number|null};
type Order = {
  id:number;organization_id:number;property_id:number;work_order_id:number;
  vendor_id:number;sku:string;item_name:string;requested_qty:number;unit_cost_cents:number;
  reason:string;status:string;requested_by_id:number;reviewed_by_id:number|null;
  decision_reason:string|null;net_received:number;physical_receipts:Movement[];
  vendor_delivery_confirmed:boolean;gl_posted:boolean;tenant_charged:boolean;
};
type Stock = {sku:string;item_name:string;quantity:number};
type Issue = {id:number;material_order_id:number;target_work_order_id:number;
  reference:string;delta_qty:number;issued_by_id:number;reverses_id:number|null;reason:string};
type StockVariance = {id:number;request_key:string;quantity:number;reason:string;
  reported_by_id:number;status:"REQUESTED"|"APPROVED"|"DENIED"|"RESTORED";
  reviewed_by_id:number|null;review_reason:string|null;restored_by_id:number|null;restore_reason:string|null};
type StockOrder = Order & {available_stock:number;net_issued:number;net_missing:number;
  material_issues:Issue[];stock_variances:StockVariance[]};

export default function MaterialOrdersPage() {
  const [actor,setActor] = useState<Actor|null>(null);
  const requestKey = useRef("");
  const [workOrder,setWorkOrder] = useState("");
  const [vendors,setVendors] = useState<Vendor[]>([]);
  const [vendorId,setVendorId] = useState("");
  const [sku,setSku] = useState("");
  const [itemName,setItemName] = useState("");
  const [quantity,setQuantity] = useState("1");
  const [unitCost,setUnitCost] = useState("0");
  const [reason,setReason] = useState("");
  const [orders,setOrders] = useState<StockOrder[]>([]);
  const [reviews,setReviews] = useState<Record<number,string>>({});
  const [receipts,setReceipts] = useState<Record<number,{reference:string;quantity:string;notes:string}>>({});
  const [allocations,setAllocations] = useState<Record<number,{reference:string;quantity:string;notes:string;target:string}>>({});
  const [variances,setVariances] = useState<Record<number,{quantity:string;reason:string}>>({});
  const varianceKeys=useRef<Record<number,string>>({});
  const [stock,setStock] = useState<{property:number;rows:Stock[]}|null>(null);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState("");
  const [message,setMessage] = useState("");

  async function refresh() {
    const result = await apiGet("/api/maintenance/materials/orders?limit=100") as StockOrder[];
    if(!Array.isArray(result))throw new Error("Invalid purchasing list");
    setStock(null);
    setOrders(result);
  }
  useEffect(()=>{
    const query = new URLSearchParams(window.location.search);
    const id = query.get("work_order_id");
    if(id && /^[1-9]\d*$/.test(id))setWorkOrder(id);
    apiGet("/auth/me").then((person:Actor)=>{
      if(!["ADMIN","OWNER","MANAGER"].includes(String(person.role).toUpperCase()))
        throw new Error("Purchasing requires an authorized staff account");
      setActor(person);
    }).catch(cause=>setError(cause instanceof Error?cause.message:"Not authorized"));
  },[]);
  useEffect(()=>{
    if(!actor)return;
    refresh().catch(cause=>setError(cause instanceof Error?cause.message:"Purchase orders unavailable"));
  },[actor]);

  async function findVendors() {
    setError("");setVendors([]);setVendorId("");
    const id=Number(workOrder);
    if(!Number.isSafeInteger(id)||id<1){setError("Enter a valid work-order number");return;}
    try{
      const result=await apiGet("/api/maintenance/materials/vendors?work_order_id="+id) as Vendor[];
      if(!Array.isArray(result))throw new Error("Invalid vendor choices");
      setVendors(result);
    }catch(cause){setError(cause instanceof Error?cause.message:"Vendor choices unavailable");}
  }

  async function submit(event:FormEvent<HTMLFormElement>) {
    event.preventDefault();if(busy)return;setBusy(true);setError("");setMessage("");
    try{
      if(!requestKey.current)requestKey.current=crypto.randomUUID();
      await apiPost("/api/maintenance/materials/orders",{
        request_key:requestKey.current,work_order_id:Number(workOrder),vendor_id:Number(vendorId),sku:sku.trim(),
        item_name:itemName.trim(),quantity:Number(quantity),unit_cost_cents:Number(unitCost),
        reason:reason.trim(),
      });
      requestKey.current="";
      setMessage("Purchase request recorded. Independent Owner/Admin review is required. No vendor was contacted.");
      setSku("");setItemName("");setReason("");
      await refresh();
    }catch(cause){setError(cause instanceof Error?cause.message:"Purchase request failed");}
    finally{setBusy(false);}
  }

  async function decide(row:Order,approved:boolean) {
    const explanation=(reviews[row.id]||"").trim();
    if(explanation.length<10){setError("Provide a review explanation of at least 10 characters");return;}
    setBusy(true);setError("");setMessage("");
    try{
      await apiPost("/api/maintenance/materials/orders/"+row.id+"/decision",{
        approved,reason:explanation,
      });
      await refresh();
      setMessage(approved?"Purchase approved internally. No supplier delivery or payment was recorded.":"Purchase request denied and audited.");
    }catch(cause){setError(cause instanceof Error?cause.message:"Review failed");}
    finally{setBusy(false);}
  }

  async function receive(event:FormEvent<HTMLFormElement>,row:Order) {
    event.preventDefault();const draft=receipts[row.id];
    if(!draft)return;setBusy(true);setError("");setMessage("");
    try{
      await apiPost("/api/maintenance/materials/orders/"+row.id+"/receive",{
        reference:draft.reference.trim(),quantity:Number(draft.quantity),notes:draft.notes.trim(),
      });
      await refresh();setStock(null);
      setMessage("Physical stock receipt attested and audited. This is not a supplier delivery confirmation or a financial posting.");
    }catch(cause){setError(cause instanceof Error?cause.message:"Receiving failed");}
    finally{setBusy(false);}
  }

  async function allocateStock(event:FormEvent<HTMLFormElement>, row:StockOrder) {
    event.preventDefault();
    const draft=allocations[row.id];
    if(!draft||busy)return;
    setBusy(true);setError("");setMessage("");
    try {
      await apiPost("/api/maintenance/materials/orders/"+row.id+"/issue",{
        target_work_order_id:Number(draft.target),
        reference:draft.reference.trim(),quantity:Number(draft.quantity),
        notes:draft.notes.trim(),
      });
      await refresh();
      setStock(null);
      setMessage("Physical stock issued to an authorized work order and audited. No GL posting or tenant charge.");
    }catch(cause){setError(cause instanceof Error?cause.message:"Stock issue failed");}
    finally{setBusy(false);}
  }

  async function proposeVariance(event:FormEvent<HTMLFormElement>,row:StockOrder) {
    event.preventDefault();
    if(busy)return;
    const draft=variances[row.id];
    if(!draft)return;
    if(!varianceKeys.current[row.id])varianceKeys.current[row.id]=crypto.randomUUID();
    setBusy(true);setError("");setMessage("");
    try {
      await apiPost("/api/maintenance/materials/orders/"+row.id+"/variances",{
        request_key:varianceKeys.current[row.id],quantity:Number(draft.quantity),
        reason:draft.reason.trim(),
      });
      delete varianceKeys.current[row.id];
      await refresh();setStock(null);
      setMessage("Stock discrepancy submitted for separate Owner/Admin approval. Physical totals have not changed.");
    }catch(cause){setError(cause instanceof Error?cause.message:"Discrepancy request failed. Original request key retained for safe retry.");}
    finally{setBusy(false);}
  }

  async function decideVariance(row:StockOrder,item:StockVariance,approved:boolean){
    const reason=window.prompt("Independent discrepancy review reason (at least 10 characters):");
    if(reason===null)return;
    if(reason.trim().length<10){setError("Review reason must be at least 10 characters.");return;}
    setBusy(true);setError("");setMessage("");
    try {
      await apiPost("/api/maintenance/materials/orders/"+row.id+"/variances/"+item.id+"/decision",{
        approved,reason:reason.trim(),
      });
      await refresh();setStock(null);
      setMessage(approved?"Stock discrepancy approved and deducted from physical available stock. No financial entry was posted.":"Discrepancy denied without inventory change.");
    }catch(cause){setError(cause instanceof Error?cause.message:"Discrepancy decision failed");}
    finally{setBusy(false);}
  }

  async function recoverVariance(row:StockOrder,item:StockVariance){
    const reason=window.prompt("Describe the physical recount or recovered material (at least 10 characters):");
    if(reason===null)return;
    if(reason.trim().length<10){setError("Physical recount reason must be at least 10 characters.");return;}
    setBusy(true);setError("");setMessage("");
    try {
      await apiPost("/api/maintenance/materials/orders/"+row.id+"/variances/"+item.id+"/restore",{
        reason:reason.trim(),
      });
      await refresh();setStock(null);
      setMessage("Separate independent restoration recorded. Original shortage testimony is unchanged. No financial entry posted.");
    }catch(cause){setError(cause instanceof Error?cause.message:"Recount recovery failed");}
    finally{setBusy(false);}
  }

  async function reverseStockIssue(row:StockOrder, issue:Issue) {
    const reason=window.prompt("Independent stock issue reversal reason (at least 10 characters):");
    if(reason===null)return;
    if(reason.trim().length<10){setError("Reason must contain at least 10 characters");return;}
    setBusy(true);setError("");setMessage("");
    try {
      await apiPost("/api/maintenance/materials/orders/"+row.id+"/issues/"+issue.id+"/reverse",{
        reason:reason.trim(),
      });
      await refresh();setStock(null);
      setMessage("Independent stock-use reversal recorded without changing original evidence or posting money.");
    }catch(cause){setError(cause instanceof Error?cause.message:"Stock issue reversal failed");}
    finally{setBusy(false);}
  }

  async function reverse(row:Order,movement:Movement){
    const reason=window.prompt("Independent correction reason (at least 10 characters):");
    if(reason===null)return;
    if(reason.trim().length<10){setError("A correction reason of at least 10 characters is required");return;}
    setBusy(true);setError("");setMessage("");
    try{
      await apiPost("/api/maintenance/materials/orders/"+row.id+"/movements/"+movement.id+"/reverse",{
        reason:reason.trim(),
      });
      await refresh();setStock(null);
      setMessage("Immutable reversing physical movement recorded. Original evidence remains.");
    }catch(cause){setError(cause instanceof Error?cause.message:"Correction failed");}
    finally{setBusy(false);}
  }

  async function inspectStock(property:number){
    setError("");
    try{
      const rows=await apiGet("/api/maintenance/materials/stock?property_id="+property) as Stock[];
      if(!Array.isArray(rows))throw new Error("Invalid stock summary");
      setStock({property,rows});
    }catch(cause){setError(cause instanceof Error?cause.message:"Unable to view property stock");}
  }

  const reviewRole = actor && ["ADMIN","OWNER"].includes(String(actor.role).toUpperCase());
  const varianceField=(id:number,field:"quantity"|"reason",value:string)=>
    setVariances(old=>{
      const previous=old[id]??{quantity:"1",reason:""};
      return {...old,[id]:{...previous,[field]:value}};
    });
  const allocationField=(id:number,field:"reference"|"quantity"|"notes"|"target",value:string)=>
    setAllocations(old=>{
      const previous=old[id] ?? {reference:"",quantity:"1",notes:"",target:""};
      return {...old,[id]:{...previous,[field]:value}};
    });
  const receiptField=(id:number,field:"reference"|"quantity"|"notes",value:string)=>
    setReceipts(old=>{
      const previous=old[id] ?? {reference:"",quantity:"1",notes:""};
      return {...old,[id]:{...previous,[field]:value}};
    });
  return <main className="space-y-5">
    <Link href="/dashboard/maintenance/work-orders" className="text-blue-800 underline">Back to maintenance work orders</Link>
    <h1 className="text-2xl font-semibold">Material purchasing and physical receipts</h1>
    <p className="text-sm text-amber-800">Internal requests, staff-attested receipts and documented work-order use only. Supplier contact, invoices, payables, GL posting and tenant charges are NOT activated. Insurance/compliance verification and real supplier delivery are separate requirements.</p>
    {error && <p role="alert" className="rounded border p-3 text-red-700">{error}</p>}
    {message && <p role="status" className="rounded border p-3">{message}</p>}
    {!actor && !error && <p role="status">Verifying staff access…</p>}
    {actor && <>
      <form onSubmit={event=>void submit(event)} className="space-y-3 rounded-lg border p-4">
        <h2 className="font-semibold">Request material for a work order</h2>
        <label className="block text-sm">Work order number
          <input aria-label="Material work order" className="mt-1 block w-full rounded border p-2"
            type="number" min="1" required value={workOrder} onChange={event=>setWorkOrder(event.target.value)}/>
        </label>
        <button type="button" onClick={()=>void findVendors()} className="rounded border px-3 py-2 text-sm">Find eligible company vendors</button>
        <label className="block text-sm">Supplier company
          <select aria-label="Material vendor" className="mt-1 block w-full rounded border p-2"
            required value={vendorId} onChange={event=>setVendorId(event.target.value)}>
            <option value="">Select an active vendor for this work order</option>
            {vendors.map(item=><option key={item.id} value={item.id}>{item.company_name}</option>)}
          </select>
        </label>
        <label className="block text-sm">Stock SKU
          <input aria-label="Material SKU" className="mt-1 block w-full rounded border p-2"
            minLength={2} maxLength={60} pattern="[A-Za-z0-9][A-Za-z0-9._-]*" required
            value={sku} onChange={event=>setSku(event.target.value)}/>
        </label>
        <label className="block text-sm">Item description
          <input aria-label="Material item name" className="mt-1 block w-full rounded border p-2"
            minLength={3} maxLength={255} required value={itemName} onChange={event=>setItemName(event.target.value)}/>
        </label>
        <label className="block text-sm">Quantity
          <input aria-label="Material requested quantity" type="number" min="1" max="10000" required
            className="mt-1 block w-full rounded border p-2" value={quantity}
            onChange={event=>setQuantity(event.target.value)}/>
        </label>
        <label className="block text-sm">Unit cost in cents (USD)
          <input aria-label="Material unit cost cents" type="number" min="0" max="100000000" required
            className="mt-1 block w-full rounded border p-2" value={unitCost}
            onChange={event=>setUnitCost(event.target.value)}/>
        </label>
        <label className="block text-sm">Business reason
          <textarea aria-label="Material request reason" className="mt-1 block w-full rounded border p-2"
            minLength={10} maxLength={1000} required value={reason}
            onChange={event=>setReason(event.target.value)}/>
        </label>
        <button type="submit" disabled={busy||!vendorId}
          className="rounded bg-slate-900 px-4 py-2 text-white disabled:opacity-50">Submit internal material request</button>
      </form>
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">Authorized purchasing history</h2>
          <button className="rounded border px-3 py-2 text-sm" type="button" onClick={()=>void refresh().catch(cause=>setError(cause instanceof Error?cause.message:"Could not refresh"))}>
            Refresh purchase history</button>
        </div>
        {orders.length===0 && <p>No material requests available for your current properties.</p>}
        {orders.map(row=><article key={row.id} className="space-y-3 rounded-lg border p-4">
          <h3 className="font-semibold">Purchase #{row.id}: {row.item_name} ({row.sku})</h3>
          <p className="text-sm">Status: {row.status} · Requested {row.requested_qty} · Net received {row.net_received} · Issued to work orders {row.net_issued} · Approved missing {row.net_missing} · Available from this request {row.available_stock} · Unit cost {(row.unit_cost_cents/100).toFixed(2)} USD</p>
          <p className="text-sm">Vendor #{row.vendor_id} · Property #{row.property_id} · Requested by user #{row.requested_by_id}</p>
          <p className="text-sm">Reason: {row.reason}</p>
          <Link className="text-sm text-blue-800 underline" href={"/dashboard/maintenance/work-orders/"+row.work_order_id}>
            Open work order #{row.work_order_id}</Link>
          {row.status==="REQUESTED" && reviewRole && actor!.id!==row.requested_by_id && <div className="space-y-2 rounded border p-3">
            <label className="block text-sm">Independent approval decision reason
              <textarea aria-label={"Material decision reason "+row.id} minLength={10} maxLength={500}
                className="mt-1 block w-full rounded border p-2" value={reviews[row.id]||""}
                onChange={event=>setReviews(old=>({...old,[row.id]:event.target.value}))}/>
            </label>
            <button disabled={busy} className="rounded border px-3 py-2 text-sm" onClick={()=>void decide(row,true)}>Approve internal request</button>
            <button disabled={busy} className="ml-2 rounded border px-3 py-2 text-sm" onClick={()=>void decide(row,false)}>Deny request</button>
          </div>}
          {row.decision_reason && <p className="text-sm">Independent decision by user #{row.reviewed_by_id}: {row.decision_reason}</p>}
          {row.status==="APPROVED" && row.net_received<row.requested_qty && <form
            onSubmit={event=>void receive(event,row)} className="space-y-2 rounded border p-3">
            <h4 className="font-semibold text-sm">Attest actual physical receipt</h4>
            <label className="block text-sm">Receipt reference
              <input required minLength={3} maxLength={100} aria-label={"Material receipt reference "+row.id}
                className="mt-1 block w-full rounded border p-2" value={receipts[row.id]?.reference||""}
                onChange={event=>receiptField(row.id,"reference",event.target.value)}/>
            </label>
            <label className="block text-sm">Received quantity
              <input required min="1" max={row.requested_qty-row.net_received} type="number"
                aria-label={"Material receipt quantity "+row.id} className="mt-1 block w-full rounded border p-2"
                value={receipts[row.id]?.quantity||"1"} onChange={event=>receiptField(row.id,"quantity",event.target.value)}/>
            </label>
            <label className="block text-sm">Physical evidence notes
              <textarea required minLength={10} maxLength={1000}
                aria-label={"Material receipt notes "+row.id} className="mt-1 block w-full rounded border p-2"
                value={receipts[row.id]?.notes||""} onChange={event=>receiptField(row.id,"notes",event.target.value)}/>
            </label>
            <button disabled={busy} className="rounded border px-3 py-2 text-sm" type="submit">Record received stock</button>
          </form>}
          {row.status==="APPROVED" && row.available_stock>0 && <form
            onSubmit={event=>void allocateStock(event,row)} className="space-y-2 rounded border p-3">
            <h4 className="font-semibold text-sm">Record actual stock use against a work order</h4>
            <p className="text-xs">Only approved stock already physically received may be used. Work order must belong to this property. This does not book a financial expense or tenant charge.</p>
            <label className="block text-sm">Target work order number
              <input required min="1" type="number" aria-label={"Material issue work order "+row.id}
                className="mt-1 block w-full rounded border p-2" value={allocations[row.id]?.target||""}
                onChange={event=>allocationField(row.id,"target",event.target.value)}/>
            </label>
            <label className="block text-sm">Issue reference
              <input required minLength={3} maxLength={100}
                aria-label={"Material issue reference "+row.id}
                className="mt-1 block w-full rounded border p-2" value={allocations[row.id]?.reference||""}
                onChange={event=>allocationField(row.id,"reference",event.target.value)}/>
            </label>
            <label className="block text-sm">Physical units used
              <input required min="1" max={row.available_stock} type="number"
                aria-label={"Material issue quantity "+row.id}
                className="mt-1 block w-full rounded border p-2" value={allocations[row.id]?.quantity||"1"}
                onChange={event=>allocationField(row.id,"quantity",event.target.value)}/>
            </label>
            <label className="block text-sm">Usage / work performed evidence
              <textarea required minLength={10} maxLength={1000}
                aria-label={"Material issue notes "+row.id}
                className="mt-1 block w-full rounded border p-2" value={allocations[row.id]?.notes||""}
                onChange={event=>allocationField(row.id,"notes",event.target.value)}/>
            </label>
            <button type="submit" disabled={busy}
              className="rounded border px-3 py-2 text-sm disabled:opacity-50">Record physical material usage</button>
          </form>}
          {row.status==="APPROVED" && row.available_stock>0 && <form
            onSubmit={event=>void proposeVariance(event,row)}
            className="space-y-2 rounded border p-3">
            <h4 className="font-semibold text-sm">Report missing physical stock for independent review</h4>
            <p className="text-xs">A report does not change stock. Only a different Owner/Admin can approve it. Physical shortage approval does not post any cost, charge or GL transaction.</p>
            <label className="block text-sm">Missing units reported
              <input aria-label={"Stock discrepancy quantity "+row.id} type="number" required min="1" max={row.available_stock}
                className="mt-1 block w-full rounded border p-2" value={variances[row.id]?.quantity||"1"}
                onChange={event=>varianceField(row.id,"quantity",event.target.value)}/>
            </label>
            <label className="block text-sm">Witnessed physical count and reason
              <textarea aria-label={"Stock discrepancy reason "+row.id} required minLength={10} maxLength={1000}
                className="mt-1 block w-full rounded border p-2" value={variances[row.id]?.reason||""}
                onChange={event=>varianceField(row.id,"reason",event.target.value)}/>
            </label>
            <button type="submit" disabled={busy} className="rounded border px-3 py-2 text-sm">Submit discrepancy for independent approval</button>
          </form>}
          {row.stock_variances.length>0 && <div className="space-y-2 rounded border p-3 text-sm">
            <h4 className="font-semibold">Physical stock discrepancy and restoration history</h4>
            {row.stock_variances.map(item=><div className="space-y-1" key={item.id}>
              <p>Report #{item.id} · {item.status} · {item.quantity} units · witness user #{item.reported_by_id} · {item.reason}</p>
              {item.reviewed_by_id && <p>Review by user #{item.reviewed_by_id}: {item.review_reason}</p>}
              {item.restored_by_id && <p>Restored by user #{item.restored_by_id}: {item.restore_reason}</p>}
              {item.status==="REQUESTED" && reviewRole && actor!.id!==item.reported_by_id &&
                <div className="flex gap-2">
                  <button type="button" disabled={busy} className="underline"
                    onClick={()=>void decideVariance(row,item,true)}>Approve counted shortage</button>
                  <button type="button" disabled={busy} className="underline"
                    onClick={()=>void decideVariance(row,item,false)}>Deny discrepancy</button>
                </div>}
              {item.status==="APPROVED" && reviewRole && actor!.id!==item.reported_by_id &&
                actor!.id!==item.reviewed_by_id &&
                <button type="button" disabled={busy} className="underline"
                  onClick={()=>void recoverVariance(row,item)}>Independently certify physical stock recovery</button>}
            </div>)}
          </div>}
          {row.material_issues.length>0 && <div className="text-sm space-y-1">
            <h4 className="font-semibold">Immutable work-order material usage</h4>
            {row.material_issues.map(issue=><p key={issue.id}>
              Usage #{issue.id} · {issue.delta_qty>0?"+":""}{issue.delta_qty} units used · {issue.reference}
              {" · "}work order #{issue.target_work_order_id} · by user #{issue.issued_by_id}
              {issue.reverses_id?" · reverses usage #"+issue.reverses_id:""}
              {issue.delta_qty>0 && reviewRole && actor!.id!==issue.issued_by_id &&
                !row.material_issues.some(previous=>previous.reverses_id===issue.id) &&
                <button type="button" disabled={busy} className="ml-2 underline"
                  onClick={()=>void reverseStockIssue(row,issue)}>Reverse material usage</button>}
            </p>)}
          </div>}
          {row.physical_receipts.length>0 && <div className="text-sm">
            <h4 className="font-semibold">Immutable physical movement history</h4>
            {row.physical_receipts.map(event=><p key={event.id}>
              #{event.id} · {event.delta_qty>0?"+":""}{event.delta_qty} units · {event.reference} · by user #{event.received_by_id}
              {event.reverses_id?" · reverses #"+event.reverses_id:""}
              {event.delta_qty>0 && reviewRole && actor!.id!==event.received_by_id &&
                !row.physical_receipts.some(other=>other.reverses_id===event.id) && (
                  <button type="button" disabled={busy} className="ml-2 underline"
                    onClick={()=>void reverse(row,event)}>Reverse receipt</button>
                )}
            </p>)}
          </div>}
          <button type="button" className="rounded border px-3 py-2 text-sm"
            onClick={()=>void inspectStock(row.property_id)}>View physical property stock</button>
          {stock?.property===row.property_id && <ul className="list-disc pl-5 text-sm">
            {stock.rows.length===0 && <li>No received materials in stock.</li>}
            {stock.rows.map(item=><li key={item.sku}>{item.sku} · {item.item_name}: {item.quantity} units</li>)}
          </ul>}
        </article>)}
      </section>
    </>}
  </main>;
}
