import {useState} from 'react';
import {Alert,Button,Checkbox,Form,Input,InputNumber,Select,Space} from '../ui';
import Disclosure from '../ui/Disclosure';
import {useData,useAction,Fault} from '../hooks';
import type {Request,Nas} from '../api';
type Assignment={nas_id:number;rate_limit:string;pool:string;interim_seconds:number;enabled:boolean};
export function PppoeFields({nas}:{nas:Nas[]}){
 return <><Form.Item name="pppoe_nas" label="PPPoE NAS" rules={[{required:true}]}><Select options={nas.filter(n=>n.type==='mikrotik'&&n.services?.includes('pppoe')).map(n=>({value:n.id,label:n.shortname}))}/></Form.Item><Form.Item name="pppoe_rate" label="Mikrotik-Rate-Limit" rules={[{required:true,pattern:/^[1-9][0-9]{0,5}M\/[1-9][0-9]{0,5}M$/}]}><Input placeholder="100M/100M"/></Form.Item><Form.Item name="pppoe_pool" label="NAS Framed-Pool" rules={[{required:true,max:64}]}><Input/></Form.Item><Form.Item name="pppoe_interim" label="Interim (сек)"><InputNumber min={60} max={86400}/></Form.Item></>
}
function Editor({request,id,nas,initial,refresh}:{request:Request;id:number;nas:Nas[];initial:Assignment|null;refresh:()=>void}){
 const [enabled,setEnabled]=useState(initial?.enabled??false);const [form]=Form.useForm();const a=useAction(refresh);
 return <Space direction="vertical" className="full"><Alert type="info" message="PAP / MS-CHAPv2. Пул должен существовать на NAS. CHAP для централизованного пароля не поддерживается."/><Form form={form} initialValues={{pppoe_nas:initial?.nas_id,pppoe_rate:initial?.rate_limit,pppoe_pool:initial?.pool,pppoe_interim:initial?.interim_seconds??300}} onFinish={v=>a.run(()=>request('identities/'+id+'/pppoe','PUT',{enabled,assignment:enabled?{nas_id:v.pppoe_nas,rate_limit:v.pppoe_rate,pool:v.pppoe_pool,interim_seconds:v.pppoe_interim??300}:null}))}><Checkbox checked={enabled} onChange={e=>setEnabled(e.target.checked)}>PPPoE</Checkbox>{enabled&&<PppoeFields nas={nas}/>}<Button type="primary" htmlType="submit" loading={a.busy}>Сохранить PPPoE</Button></Form></Space>
}
export default function IdentityPppoe({request,id,refresh}:{request:Request;id:number;refresh:()=>void}){
 const d=useData<Assignment|null>(request,'identities/'+id+'/pppoe');const n=useData<Nas[]>(request,'nas');
 return <Disclosure title="PPPoE — абонентский доступ"><Fault error={d.error||n.error}/>{!d.loading&&d.data!==undefined&&n.data&&<Editor request={request} id={id} nas={n.data} initial={d.data} refresh={()=>{d.refresh();refresh()}}/>}</Disclosure>
}
