import {useState} from 'react';
import {Alert,Button,Checkbox,Input,Select,Space,Popconfirm} from '../ui';
import {useData,useAction,Fault} from '../hooks';
import type {Request} from '../api';
import IdentitySessions from './IdentitySessions';
type User={id:number;username:string;full_name:string;enabled:boolean};
type Result={preview:boolean;enabled:boolean;selected:number;changed:number;web_sessions_revoked:number;network_disconnected:boolean};
type Plan={identity_ids:number[];enabled:boolean};
export default function IdentityBulkState({request,refresh}:{request:Request;refresh:()=>void}){
 const [query,setQuery]=useState('');const [search,setSearch]=useState('');const [offset,setOffset]=useState(0);
 const [enabled,setEnabled]=useState(false);const [selected,setSelected]=useState<User[]>([]);
 const [plan,setPlan]=useState<Plan>();const [result,setResult]=useState<Result>();const [blocked,setBlocked]=useState<User[]>([]);const [sessionId,setSessionId]=useState<number>();
 const d=useData<User[]>(request,'identities?limit=101&offset='+offset+'&q='+encodeURIComponent(search)+'&enabled='+String(!enabled));
 const a=useAction(()=>{});
 const invalidate=()=>{setPlan(undefined);setResult(undefined)};
 return <Space direction="vertical" className="full">
 <Alert type="warning" message="До 100 пользователей. Блокировка сохраняет назначения, отзывает веб-сессии, но не завершает автоматически сетевые сессии. Требуется персональный администратор."/>
 <Fault error={d.error}/>
 <Select value={enabled?'enable':'disable'} disabled={a.busy} options={[{value:'disable',label:'Заблокировать'},{value:'enable',label:'Разблокировать'}]} onChange={v=>{invalidate();setEnabled(v==='enable');setOffset(0);setSelected([])}}/>
 <Space wrap><Input value={query} maxLength={200} placeholder="Поиск пользователя" onChange={e=>setQuery(e.target.value)}/><Button onClick={()=>{setOffset(0);setSearch(query.trim())}}>Найти</Button></Space>
 {(d.data??[]).slice(0,100).map(user=><Checkbox key={user.id} checked={selected.some(x=>x.id===user.id)} disabled={a.busy||selected.length>=100&&!selected.some(x=>x.id===user.id)} onChange={e=>{invalidate();setSelected(old=>e.target.checked?[...old,user]:old.filter(x=>x.id!==user.id))}}>{user.username} — {user.full_name}</Checkbox>)}
 <Space wrap><Button disabled={!offset||d.loading} onClick={()=>setOffset(x=>Math.max(0,x-100))}>Назад</Button><Button disabled={d.loading||(d.data?.length??0)<=100} onClick={()=>setOffset(x=>x+100)}>Далее</Button><span>Выбрано: {selected.length}</span><Button disabled={a.busy} onClick={()=>{invalidate();setSelected([])}}>Очистить</Button></Space>
 <span>{selected.map(x=>x.username).join(', ')}</span>
 <Button loading={a.busy} disabled={!selected.length||a.busy} onClick={()=>{invalidate();const payload={identity_ids:selected.map(x=>x.id),enabled};return a.run(async()=>{const res=await request<Result>('identities/bulk-state','POST',{...payload,preview:true});setPlan(payload);setResult(res)})}}>Проверить</Button>
 {plan&&result?.preview&&<><Alert type="info" message={'Изменится записей: '+result.changed+'; веб-сессий к отзыву: '+result.web_sessions_revoked}/><Popconfirm title={plan.enabled?'Разблокировать выбранных пользователей?':'Заблокировать выбранных пользователей и отозвать веб-сессии?'} onConfirm={()=>a.run(async()=>{const res=await request<Result>('identities/bulk-state','POST',{...plan,preview:false});if(!plan.enabled){setBlocked(selected);setSessionId(undefined)}else{setBlocked([]);setSessionId(undefined)}setResult(res);setPlan(undefined);setSelected([]);setOffset(0);d.refresh();refresh()})}><Button type="primary" danger={!plan.enabled} disabled={a.busy}>Применить</Button></Popconfirm></>}
 {result&&!result.preview&&<Alert type="success" message={'Изменено: '+result.changed+'; веб-сессий отозвано: '+result.web_sessions_revoked}/>}
 {blocked.length>0&&<><Alert type="info" message="Проверьте открытые Accounting-сессии заблокированных пользователей и при необходимости отправьте отдельный Disconnect-Request."/><Select value={sessionId} placeholder="Пользователь для проверки сессий" options={blocked.map(x=>({value:x.id,label:x.username}))} onChange={v=>setSessionId(Number(v))}/>{sessionId&&<IdentitySessions key={sessionId} request={request} id={sessionId}/>}</>}
 </Space>
}
