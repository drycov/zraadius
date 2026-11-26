import {useState} from 'react';
import {Alert,Button,Checkbox,Form,InputNumber,Select,Space} from '../ui';
import Disclosure from '../ui/Disclosure';
import {useData,useAction,Fault} from '../hooks';
import type {Request,Nas} from '../api';
type Service='dot1x'|'wpa-enterprise';
type Assignment={nas_id:number;vlan_id:number|null;enabled:boolean};
const label=(s:Service)=>s==='dot1x'?'802.1X':'WPA Enterprise';
export function EapFields({nas,service}:{nas:Nas[];service:Service}){
 return <><Form.Item name={service+'_nas'} label={label(service)+' NAS'} rules={[{required:true}]}><Select options={nas.filter(n=>n.services?.includes(service)&&!n.services?.includes(service==='dot1x'?'wpa-enterprise':'dot1x')).map(n=>({value:n.id,label:n.shortname}))}/></Form.Item><Form.Item name={service+'_vlan'} label={label(service)+' VLAN'}><InputNumber min={1} max={4094}/></Form.Item></>
}
function Editor({request,id,service,nas,initial,refresh}:{request:Request;id:number;service:Service;nas:Nas[];initial:Assignment|null;refresh:()=>void}){
 const [enabled,setEnabled]=useState(initial?.enabled??false);const [form]=Form.useForm();const a=useAction(refresh);
 return <Space direction="vertical" className="full"><Alert type="info" message="PEAP-MSCHAPv2. NAS должен иметь только один из двух EAP-сервисов. Проверка сертификата сервера обязательна на клиенте."/><Form form={form} initialValues={{[service+'_nas']:initial?.nas_id,[service+'_vlan']:initial?.vlan_id}} onFinish={v=>a.run(()=>request('identities/'+id+'/eap/'+service,'PUT',{enabled,assignment:enabled?{nas_id:v[service+'_nas'],vlan_id:v[service+'_vlan']||null}:null}))}><Checkbox checked={enabled} onChange={e=>setEnabled(e.target.checked)}>{label(service)}</Checkbox>{enabled&&<EapFields nas={nas} service={service}/>}<Button type="primary" htmlType="submit" loading={a.busy}>Сохранить {label(service)}</Button></Form></Space>
}
export default function IdentityEap({request,id,service,refresh}:{request:Request;id:number;service:Service;refresh:()=>void}){
 const d=useData<Assignment|null>(request,'identities/'+id+'/eap/'+service);const n=useData<Nas[]>(request,'nas');
 return <Disclosure title={label(service)+' — сетевой доступ'}><Fault error={d.error||n.error}/>{!d.loading&&d.data!==undefined&&n.data&&<Editor request={request} id={id} service={service} nas={n.data} initial={d.data} refresh={()=>{d.refresh();refresh()}}/>}</Disclosure>
}
