import {useState} from 'react';
import {Alert,Button,Input,Select,Space,Popconfirm} from '../ui';
import {useData,useAction,Fault} from '../hooks';
import type {Request} from '../api';
type User={id?:number;username:string;enabled:boolean};
type Result={preview:boolean;username:string;service:string;legacy_enabled:boolean;identity_enabled:boolean;identity_id?:number};
export default function IdentityLegacy({request,refresh}:{request:Request;refresh:()=>void}){
 const [service,setService]=useState('device');const [q,setQ]=useState('');const [search,setSearch]=useState('');const [offset,setOffset]=useState(0);
 const [plan,setPlan]=useState<{service:string;user_id?:number;username?:string}>();const [result,setResult]=useState<Result>();const [password,setPassword]=useState('');
 const d=useData<User[]>(request,(service==='eap'?'identities/legacy-eap-candidates?':'identities/legacy-candidates?service='+service+'&')+'&q='+encodeURIComponent(search)+'&limit=101&offset='+offset);
 const a=useAction(()=>{});
 const reset=()=>{setPlan(undefined);setResult(undefined);setPassword('')};
 return <Space direction="vertical" className="full">
 <Alert type="warning" message="Перенос одной независимой записи без объединения совпадающих логинов. Новый единый пользователь будет заблокирован до ручного включения. Старый пароль перестанет действовать; активные сетевые сессии могут сохраниться. При переносе IAM веб-сессии отзываются; последний активный администратор защищён."/>
 <Fault error={d.error}/>
 <Select value={service} disabled={a.busy} options={[{value:'device',label:'Device AAA'},{value:'l2tp',label:'L2TP VPN'},{value:'console',label:'Web Console / IAM'},{value:'eap',label:'Legacy EAP'}]} onChange={v=>{reset();setService(String(v));setOffset(0)}}/>
 <Space wrap><Input value={q} maxLength={200} placeholder="Логин" onChange={e=>setQ(e.target.value)}/><Button onClick={()=>{setOffset(0);setSearch(q.trim())}}>Найти</Button></Space>
 {(d.data??[]).slice(0,100).map(user=><Space key={user.id??user.username} wrap><span>{user.username} — {user.enabled?'активен':'отключён'}</span><Button disabled={a.busy} onClick={()=>{reset();const payload=service==='eap'?{service,username:user.username}:{service,user_id:user.id};return a.run(async()=>{const res=await request<Result>(service==='eap'?'identities/legacy-eap-migrate':'identities/legacy-migrate','POST',service==='eap'?{username:user.username,preview:true}:{...payload,preview:true});setPlan(payload);setResult(res)})}}>Проверить перенос</Button></Space>)}
 <Space wrap><Button disabled={!offset||d.loading} onClick={()=>setOffset(x=>Math.max(0,x-100))}>Назад</Button><Button disabled={d.loading||(d.data?.length??0)<=100} onClick={()=>setOffset(x=>x+100)}>Далее</Button></Space>
 {plan&&result?.preview&&<><Alert type="info" message={'Проверен логин: '+result.username+'. Назначения сохраняются; требуется новый пароль.'}/><Input.Password value={password} autoComplete="new-password" maxLength={128} disabled={a.busy} placeholder="Новый единый пароль (16–128 символов)" onChange={e=>setPassword(e.target.value)}/><Popconfirm title="Перенести запись и заменить пароль? Новый пользователь останется заблокирован." onConfirm={()=>a.run(async()=>{const res=await request<Result>(plan.service==='eap'?'identities/legacy-eap-migrate':'identities/legacy-migrate','POST',plan.service==='eap'?{username:plan.username,password,preview:false}:{...plan,password,preview:false});setPassword('');setPlan(undefined);setResult(res);d.refresh();refresh()})}><Button danger type="primary" disabled={a.busy||password.length<16}>Перенести</Button></Popconfirm></>}
 {result&&!result.preview&&<Alert type="success" message={'Перенесён '+result.username+'; включите пользователя вручную в каталоге.'}/>}
 </Space>
}
