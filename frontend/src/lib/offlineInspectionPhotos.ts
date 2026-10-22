"use client";
export type PendingPhoto = { key:string; inspection:number; user:number; org:number; name:string; mime:string; body:Blob };
const DB="private-inspection-pending-v1", STORE="photos";
async function run<T>(mode:IDBTransactionMode,fn:(store:IDBObjectStore,ok:(v:T)=>void,bad:(e:unknown)=>void)=>void):Promise<T>{
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
      fn(tx.objectStore(STORE),(v)=>{result=v;},reject);
    };
  });
}
export async function pendingPhotos(user:number,org:number,inspection:number):Promise<PendingPhoto[]>{
  const all=await run<PendingPhoto[]>("readonly",(s,ok,bad)=>{
    const q=s.getAll();q.onsuccess=()=>ok(q.result as PendingPhoto[]);q.onerror=()=>bad(q.error);
  });
  return all.filter(x=>x.user===user&&x.org===org&&x.inspection===inspection);
}
export async function savePending(user:number,org:number,inspection:number,file:File){
  if(!user||!org||!inspection)throw new Error("Staff identity required");
  if(!["image/jpeg","image/png","image/webp"].includes(file.type)||file.size===0||file.size>10*1024*1024)
    throw new Error("Select a JPEG, PNG or WebP photo under 10 MB");
  if((await pendingPhotos(user,org,inspection)).length>=20)throw new Error("20 unsent photos maximum");
  await run<void>("readwrite",(s,ok,bad)=>{
    const q=s.put({key:crypto.randomUUID(),user,org,inspection,name:file.name,mime:file.type,body:file} satisfies PendingPhoto);
    q.onsuccess=()=>ok();q.onerror=()=>bad(q.error);
  });
}
export async function discardPending(key:string){
  await run<void>("readwrite",(s,ok,bad)=>{
    const q=s.delete(key);q.onsuccess=()=>ok();q.onerror=()=>bad(q.error);
  });
}
