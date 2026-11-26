import {useState} from 'react';
import {Alert,Button,Checkbox,Form,Input,Select,Space} from '../ui';
import {useData,useAction,Fault} from '../hooks';
import type {Request,Nas} from '../api';
import {PppoeFields} from './IdentityPppoe';
import {HotspotFields} from './IdentityHotspot';
import {EapFields} from './IdentityEap';
type User={id:number;username:string;full_name:string;enabled:boolean};
type Result={preview:boolean;identities:number;services:string[];assignments:number};
export default function IdentityBulk({request,refresh}:{request:Request;refresh:()=>void}){
 const [q,setQ]=useState('');const [search,setSearch]=useState('');const [offset,setOffset]=useState(0);
 const d=useData<User[]>(request,'identities?enabled=true&limit=101&offset='+offset+'&q='+encodeURIComponent(search));
 const n=useData<Nas[]>(request,'nas');const p=useData<{id:number;name:string}[]>(request,'ppp/profiles');const r=useData<{name:string}[]>(request,'device-aaa/roles');
 const [selected,setSelected]=useState<User[]>([]);const [services,setServices]=useState<string[]>([]);
 const [plan,setPlan]=useState<Record<string,unknown>>();const [result,setResult]=useState<Result>();const [form]=Form.useForm();
 const a=useAction(()=>{});const nas=n.data??[];
 const options=(service:string)=>nas.filter(x=>x.type==='mikrotik'&&x.services?.includes(service)).map(x=>({value:x.id,label:x.shortname}));
 const invalidate=()=>{setPlan(undefined);setResult(undefined)};
 const toggle=(user:User,checked:boolean)=>{invalidate();setSelected(old=>checked?[...old,user]:old.filter(x=>x.id!==user.id))};
 return <Space direction="vertical" className="full">
 <Alert type="warning" message="Только новые назначения. Существующие политики не заменяются. При любом конфликте весь пакет откатывается. До 100 пользователей."/>
 <Fault error={d.error||n.error||p.error||r.error}/>
 <Space wrap><Input value={q} maxLength={200} placeholder="Поиск пользователя" onChange={e=>setQ(e.target.value)}/><Button onClick={()=>{setOffset(0);setSearch(q.trim())}}>Найти</Button></Space>
 <Space direction="vertical" className="full">{(d.data??[]).slice(0,100).map(user=><Checkbox key={user.id} checked={selected.some(x=>x.id===user.id)} disabled={a.busy||selected.length>=100&&!selected.some(x=>x.id===user.id)} onChange={e=>toggle(user,e.target.checked)}>{user.username} — {user.full_name}</Checkbox>)}</Space>
 <Space wrap><Button disabled={offset===0||d.loading} onClick={()=>setOffset(x=>Math.max(0,x-100))}>Назад</Button><Button disabled={d.loading||(d.data?.length??0)<=100} onClick={()=>setOffset(x=>x+100)}>Далее</Button><span>Выбрано: {selected.length}</span><Button disabled={a.busy} onClick={()=>{invalidate();setSelected([])}}>Очистить</Button></Space>
 <span>{selected.map(x=>x.username).join(', ')}</span>
 <Form form={form} layout="vertical" disabled={a.busy} onFinish={v=>{
 const has=(s:string)=>services.includes(s);
 const payload={identity_ids:selected.map(x=>x.id),device:has('device')?{nas_id:v.device_nas,role:v.device_role,filter_id:v.filter_id||null}:null,l2tp:has('l2tp')?{nas_id:v.vpn_nas,profile_id:v.vpn_profile}:null,pppoe:has('pppoe')?{nas_id:v.pppoe_nas,rate_limit:v.pppoe_rate,pool:v.pppoe_pool,interim_seconds:v.pppoe_interim??300}:null,hotspot:has('hotspot')?{nas_id:v.hotspot_nas,rate_limit:v.hotspot_rate,session_seconds:v.hotspot_session??3600,idle_seconds:v.hotspot_idle??300}:null,dot1x:has('dot1x')?{nas_id:v.dot1x_nas,vlan_id:v.dot1x_vlan||null}:null,wpa_enterprise:has('wpa-enterprise')?{nas_id:v['wpa-enterprise_nas'],vlan_id:v['wpa-enterprise_vlan']||null}:null};
 invalidate();return a.run(async()=>{const res=await request<Result>('identities/bulk-assign','POST',{...payload,preview:true});setPlan(payload);setResult(res)})
 }}>
 {['device','l2tp','pppoe','hotspot','dot1x','wpa-enterprise'].map(s=><Checkbox key={s} checked={services.includes(s)} disabled={a.busy} onChange={e=>{invalidate();setServices(old=>e.target.checked?[...old,s]:old.filter(x=>x!==s))}}>{s}</Checkbox>)}
 {services.includes('device')&&<><Form.Item name="device_nas" label="Device NAS" rules={[{required:true}]}><Select options={options('device-aaa')}/></Form.Item><Form.Item name="device_role" label="Role" rules={[{required:true}]}><Select options={(r.data??[]).map(x=>({value:x.name,label:x.name}))}/></Form.Item><Form.Item name="filter_id" label="Filter-Id"><Input/></Form.Item></>}
 {services.includes('l2tp')&&<><Form.Item name="vpn_nas" label="VPN NAS" rules={[{required:true}]}><Select options={options('l2tp')}/></Form.Item><Form.Item name="vpn_profile" label="PPP Profile" rules={[{required:true}]}><Select options={(p.data??[]).map(x=>({value:x.id,label:x.name}))}/></Form.Item></>}
 {services.includes('pppoe')&&<PppoeFields nas={nas}/>}
 {services.includes('hotspot')&&<HotspotFields nas={nas}/>}
 {services.includes('dot1x')&&<EapFields nas={nas} service="dot1x"/>}
 {services.includes('wpa-enterprise')&&<EapFields nas={nas} service="wpa-enterprise"/>}
 <Button htmlType="submit" disabled={!selected.length||!services.length||a.busy} loading={a.busy}>Проверить пакет</Button>
 </Form>
 {plan&&result?.preview&&<><Alert type="info" message={'Проверено назначений: '+result.assignments+'. Применяется именно сохранённый снимок проверки, а не последующие изменения полей.'}/><pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{JSON.stringify(plan,null,2)}</pre><Button type="primary" loading={a.busy} disabled={a.busy} onClick={()=>a.run(async()=>{const res=await request<Result>('identities/bulk-assign','POST',{...plan,preview:false});setPlan(undefined);setResult(res);setSelected([]);d.refresh();refresh()})}>Применить проверенный пакет</Button></>}
 {result&&!result.preview&&<Alert type="success" message={'Назначено сервисов: '+result.assignments}/>}
 </Space>
}
