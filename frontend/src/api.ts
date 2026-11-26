export class ApiError extends Error {
 constructor(public status:number,public detail?:string){super('HTTP '+status+(detail?' — '+detail:''))}
}
export function client(token:string,onUnauthorized?:()=>void){
 return async function request<T>(path:string,method='GET',body?:unknown):Promise<T>{
  const response=await fetch('/api/v1/'+path,{method,headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),cache:'no-store'});
  if(response.status===401&&token&&onUnauthorized)onUnauthorized();
  if(!response.ok){
   let detail:string|undefined;
   try{const result:unknown=await response.json();if(result&&typeof result==='object'&&'detail' in result&&typeof result.detail==='string')detail=result.detail.slice(0,500)}catch{/* Non-JSON upstream response */}
   throw new ApiError(response.status,detail);
  }
  return response.json() as Promise<T>;
 }
}
export type Request=ReturnType<typeof client>;
export type User={username:string;enabled:boolean};
export type Group={name:string};
export type Nas={id:number;nasname:string;shortname:string;type:string;description:string;services?:string[]};
export type Session={radacctid:number;username:string;acctsessionid:string;nasipaddress:string;framedipaddress:string|null;acctstarttime:string|null;acctstoptime:string|null;acctinputoctets:number|null;acctoutputoctets:number|null};
export type Audit={id:number;action:string;subject:string;created_at:string};
export type Dashboard=Record<'users'|'disabled_users'|'groups'|'nas'|'open_sessions'|'accounting_records'|'audit_24h',number>;
export type Attribute={name:string;vendor:number;type:string;list:string};
