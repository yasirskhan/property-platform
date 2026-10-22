"use client";

/** Unsent private evidence lives only in this browser, never in a shared account store. */
export type PendingPhoto = { key:string; inspection:number; user:number; org:number; name:string; mime:string; body:Blob };
const DB="private-inspection-pending-v1", STORE="photos";

async function run<T>(
  mode: IDBTransactionMode,
  fn:(store:IDBObjectStore,ok:(v:T)=>void,bad:(e:unknown)=>void)=>void,
):Promise<T> {
  return new Promise((resolve,reject)=>{
    const open=indexedDB.open(DB,1);
    open.onupgradeneeded=()=>open.result.createObjectStore(STORE,{keyPath:"key"});
    open.onerror=()=>reject(open.error);
    open.onsuccess=()=>{
      const db=open.result, tx=db.transaction(STORE,mode);
      let result:T;
      tx.onerror=()=>{db.close();reject(tx.error);};
      tx.onabort=()=>{db.close();reject(tx.error);};
      tx.oncomplete=()=>{db.close();resolve(result);};
      try {
        fn(tx.objectStore(STORE),(v)=>{result=v;},reject);
      } catch (e) {tx.abort();reject(e);}
    };
  });
}

function sameScope(item:PendingPhoto,user:number,org:number,inspection:number) {
  return item.user===user && item.org===org && item.inspection===inspection;
}
function validScope(user:number,org:number,inspection:number) {
  if (![user,org,inspection].every(x=>Number.isSafeInteger(x)&&x>0))
    throw new Error("Staff account and inspection scope required");
}

export async function pendingPhotos(user:number,org:number,inspection:number):Promise<PendingPhoto[]> {
  validScope(user,org,inspection);
  const all=await run<PendingPhoto[]>("readonly",(store,ok,bad)=>{
    const q=store.getAll();
    q.onsuccess=()=>ok(q.result as PendingPhoto[]);q.onerror=()=>bad(q.error);
  });
  return all.filter(item=>sameScope(item,user,org,inspection));
}

export async function savePending(user:number,org:number,inspection:number,file:File) {
  validScope(user,org,inspection);
  if(!["image/jpeg","image/png","image/webp"].includes(file.type)||file.size===0||file.size>10*1024*1024)
    throw new Error("Select a JPEG, PNG or WebP photo under 10 MB");
  // Count and insert in ONE readwrite transaction; two open tabs cannot bypass
  // the 20-item cap with simultaneous reads followed by separate writes.
  await run<void>("readwrite",(store,ok,bad)=>{
    let count=0;
    const cursor=store.openCursor();
    cursor.onerror=()=>bad(cursor.error);
    cursor.onsuccess=()=>{
      const row=cursor.result;
      if(row) {
        if(sameScope(row.value as PendingPhoto,user,org,inspection)) count++;
        if(count>=20){bad(new Error("20 unsent photos maximum"));return;}
        row.continue();
        return;
      }
      const q=store.add({key:crypto.randomUUID(),user,org,inspection,name:file.name,mime:file.type,body:file} satisfies PendingPhoto);
      q.onsuccess=()=>ok();q.onerror=()=>bad(q.error);
    };
  });
}

export async function discardPending(key:string,user:number,org:number,inspection:number) {
  validScope(user,org,inspection);
  if(!key)throw new Error("Local photo identity required");
  await run<void>("readwrite",(store,ok,bad)=>{
    const q=store.get(key);
    q.onerror=()=>bad(q.error);
    q.onsuccess=()=>{
      const saved=q.result as PendingPhoto|undefined;
      if(!saved){ok();return;} // Confirmed retries may already have removed it.
      if(!sameScope(saved,user,org,inspection)){
        bad(new Error("Cannot delete evidence belonging to another account or inspection"));
        return;
      }
      const deleted=store.delete(key);
      deleted.onsuccess=()=>ok();deleted.onerror=()=>bad(deleted.error);
    };
  });
}
