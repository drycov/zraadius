import {useState} from 'react';
import {Alert,Button,Checkbox,Form,Input,InputNumber,Select,Space} from '../ui';
import Disclosure from '../ui/Disclosure';
import {useData,useAction,Fault} from '../hooks';
import type {Request,Nas} from '../api';
type Assignment={nas_id:number;rate_limit:string;session_seconds:number;idle_seconds:number;enabled:boolean};
export function HotspotFields({nas}:{nas:Nas[]}){
 return <><Form.Item name="hotspot_nas" label="Hotspot NAS" rules={[{required:true}]}><Select options={nas.filter(n=>n.type==='mikrotik'&&n.services?.includes('hotspot')).map(n=>({value:n.id,label:n.shortname}))}/></Form.Item><Form.Item name="hotspot_rate" label="Mikrotik-Rate-Limit" rules={[{required:true,pattern:/^[1-9][0-9]{0,5}M\/[1-9][0-9]{0,5}M$/}]}><Input placeholder="20M/20M"/></Form.Item><Form.Item name="hotspot_session" label="Session Timeout (сек)"><InputNumber min={60} max={86400} placeholder="3600"/></Form.Item><Form.Item name="hotspot_idle" label="Idle Timeout (сек)"><InputNumber min={60} max={86400} placeholder="300"/></Form.Item></>
}
function Editor({request,id,nas,initial,refresh}:{request:Request;id:number;nas:Nas[];initial:Assignment|null;refresh:()=>void}){
 const [enabled,setEnabled]=useState(initial?.enabled??false);const [form]=Form.useForm();const a=useAction(refresh);
 return <Space direction="vertical" className="full"><Alert type="info" message="Постоянный доступ через единый пароль. PAP; временные ваучеры остаются отдельными."/><Form form={form} initialValues={{hotspot_nas:initial?.nas_id,hotspot_rate:initial?.rate_limit,hotspot_session:initial?.session_seconds??3600,hotspot_idle:initial?.idle_seconds??300}} onFinish={v=>a.run(()=>request('identities/'+id+'/hotspot','PUT',{enabled,assignment:enabled?{nas_id:v.hotspot_nas,rate_limit:v.hotspot_rate,session_seconds:v.hotspot_session??3600,idle_seconds:v.hotspot_idle??300}:null}))}><Checkbox checked={enabled} onChange={e=>setEnabled(e.target.checked)}>Hotspot</Checkbox>{enabled&&<HotspotFields nas={nas}/>}<Button type="primary" htmlType="submit" loading={a.busy}>Сохранить Hotspot</Button></Form></Space>
}
export default function IdentityHotspot({request,id,refresh}:{request:Request;id:number;refresh:()=>void}){
 const d=useData<Assignment|null>(request,'identities/'+id+'/hotspot');const n=useData<Nas[]>(request,'nas');
 return <Disclosure title="Hotspot — постоянный доступ"><Fault error={d.error||n.error}/>{!d.loading&&d.data!==undefined&&n.data&&<Editor request={request} id={id} nas={n.data} initial={d.data} refresh={()=>{d.refresh();refresh()}}/>}</Disclosure>
}
