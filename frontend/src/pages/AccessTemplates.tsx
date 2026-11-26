import {useState} from 'react';
import {Alert,Button,Checkbox,Input,Select,Space,Table,Tag} from '../ui';
import {useAction,useData,Fault} from '../hooks';
import type {Request,Nas} from '../api';
export const serviceCodes=['device-aaa','l2tp','pppoe','hotspot','dot1x','wpa-enterprise','console'] as const;
type ServiceParams={nas_id?:number;role?:string;filter_id?:string;profile_id?:number;rate_limit?:string;pool?:string;interim_seconds?:number;session_seconds?:number;idle_seconds?:number;vlan_id?:number};
export type TemplateParameters={device?:ServiceParams;l2tp?:ServiceParams;pppoe?:ServiceParams;hotspot?:ServiceParams;dot1x?:ServiceParams;wpa_enterprise?:ServiceParams;console_role?:string};
export type AccessTemplate={id:number;name:string;account_type:'person'|'service';description:string;services:string[];enabled:boolean;parameters:TemplateParameters};
export default function AccessTemplates({request,refresh}:{request:Request;refresh:()=>void}){
 const path='identities/access-templates';
 const d=useData<AccessTemplate[]>(request,path);
 const a=useAction(()=>{d.refresh();refresh()});
 const n=useData<Nas[]>(request,'nas');const p=useData<{id:number;name:string}[]>(request,'ppp/profiles');const roles=useData<{name:string}[]>(request,'device-aaa/roles');
 const [params,setParams]=useState<TemplateParameters>({});
 const [editing,setEditing]=useState<number>();
 const [name,setName]=useState('');const [description,setDescription]=useState('');const [kind,setKind]=useState<'person'|'service'>('person');const [services,setServices]=useState<string[]>([]);const [enabled,setEnabled]=useState(true);
 const reset=()=>{setEditing(undefined);setName('');setDescription('');setKind('person');setServices([]);setEnabled(true);setParams({})};
 return <Space direction="vertical" className="full">
 <Alert type="info" message="Шаблон заполняет форму создания УЗ. Не предоставляет доступ сам по себе и не изменяет существующие назначения."/>
 <Fault error={d.error||n.error||p.error||roles.error}/>
 <Table<AccessTemplate> rowKey="id" loading={d.loading} dataSource={d.data??[]} columns={[{title:'Шаблон',dataIndex:'name'},{title:'Тип',dataIndex:'account_type'},{title:'Услуги',render:(_,r)=><Space wrap>{r.services.map(s=><Tag key={s}>{s}</Tag>)}</Space>},{title:'Состояние',render:(_,r)=><Tag color={r.enabled?'green':'red'}>{r.enabled?'Активен':'Отключён'}</Tag>},{title:'Действия',render:(_,r)=><Button disabled={a.busy} onClick={()=>{setEditing(r.id);setName(r.name);setDescription(r.description);setKind(r.account_type);setServices(r.services);setEnabled(r.enabled);setParams(r.parameters??{})}}>Изменить</Button>}]}/>
 <label>Название<Input value={name} maxLength={100} onChange={e=>setName(e.target.value)}/></label>
 <label>Описание<Input value={description} maxLength={500} onChange={e=>setDescription(e.target.value)}/></label>
 <Select value={kind} onChange={v=>{setKind(v==='service'?'service':'person');if(v==='service')setServices(old=>old.filter(s=>s!=='console'))}} options={[{value:'person',label:'Персональная УЗ'},{value:'service',label:'Сервисная УЗ'}]}/>
 <Space wrap>{serviceCodes.map(s=><Checkbox key={s} disabled={a.busy||(kind==='service'&&s==='console')} checked={services.includes(s)} onChange={e=>setServices(old=>e.target.checked?[...old,s]:old.filter(x=>x!==s))}>{s}</Checkbox>)}</Space>
 {services.filter(s=>s!=='console').map(s=>{
 const key=(s==='device-aaa'?'device':s==='wpa-enterprise'?'wpa_enterprise':s) as Exclude<keyof TemplateParameters,'console_role'>;
 const value=params[key];
 const patch=(v:ServiceParams)=>setParams(old=>({...old,[key]:{...old[key],...v}}));
 return <Space key={s} direction="vertical" className="full"><Checkbox checked={!!value} onChange={e=>setParams(old=>({...old,[key]:e.target.checked?{}:undefined}))}>Параметры {s}</Checkbox>{value&&<>
 <label>NAS</label><Select value={value.nas_id} options={(n.data??[]).filter(x=>x.services?.includes(s)&&(s==='dot1x'||s==='wpa-enterprise'||x.type==='mikrotik')).map(x=>({value:x.id,label:x.shortname}))} onChange={v=>patch({nas_id:Number(v)})}/>
 {s==='device-aaa'&&<><label>RouterOS Role</label><Select value={value.role} options={(roles.data??[]).map(x=>({value:x.name,label:x.name}))} onChange={v=>patch({role:String(v),profile_id:undefined})}/><label>Filter-Id<Input value={value.filter_id??''} onChange={e=>patch({filter_id:e.target.value||undefined})}/></label></>}
 {s==='l2tp'&&<><label>PPP Profile</label><Select value={value.profile_id} options={(p.data??[]).map(x=>({value:x.id,label:x.name}))} onChange={v=>patch({profile_id:Number(v)})}/></>}
 {(s==='pppoe'||s==='hotspot')&&<label>Rate Limit<Input value={value.rate_limit??''} placeholder="100M/100M" onChange={e=>patch({rate_limit:e.target.value})}/></label>}
 {s==='pppoe'&&<><label>Pool<Input value={value.pool??''} onChange={e=>patch({pool:e.target.value})}/></label><label>Interim<Input value={String(value.interim_seconds??300)} onChange={e=>patch({interim_seconds:Number(e.target.value)})}/></label></>}
 {s==='hotspot'&&<><label>Session Timeout<Input value={String(value.session_seconds??3600)} onChange={e=>patch({session_seconds:Number(e.target.value)})}/></label><label>Idle Timeout<Input value={String(value.idle_seconds??300)} onChange={e=>patch({idle_seconds:Number(e.target.value)})}/></label></>}
 {(s==='dot1x'||s==='wpa-enterprise')&&<label>VLAN<Input value={String(value.vlan_id??'')} onChange={e=>patch({vlan_id:e.target.value?Number(e.target.value):undefined})}/></label>}
 </>}</Space>
 })}
 {services.includes('console')&&<><label>Роль Web Console</label><Select value={params.console_role??'manual'} options={['manual','auditor','operator','admin'].map(x=>({value:x,label:x}))} onChange={v=>setParams(old=>({...old,console_role:v==='manual'?undefined:String(v)}))}/></>}
 <Checkbox checked={enabled} onChange={e=>setEnabled(e.target.checked)}>Активный шаблон</Checkbox>
 <Space wrap><Button type="primary" disabled={!name.trim()||a.busy} onClick={()=>a.run(()=>request(editing?path+'/'+editing:path,editing?'PUT':'POST',{name,description,account_type:kind,services,enabled,parameters:Object.fromEntries(Object.entries(params).filter(([k,v])=>v!==undefined&&services.includes(k==='device'?'device-aaa':k==='wpa_enterprise'?'wpa-enterprise':k==='console_role'?'console':k)))}),reset)}>{editing?'Сохранить':'Создать шаблон'}</Button><Button disabled={a.busy} onClick={reset}>Сбросить</Button></Space>
 </Space>
}
