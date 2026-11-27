import {useState} from 'react';
import {Alert,Button,Select,Space,Table,Tag} from '../ui';
import {useData,Fault} from '../hooks';
import type {Request,Nas} from '../api';
type Target={nas_id:number;shortname:string;source:string;eligible:boolean};
type Service={service:string;assigned:boolean;enabled:boolean;credential_ready:boolean;status:'configured'|'blocked';reasons:string[];targets:Target[]};
type Policy={identity:{username:string;enabled:boolean;pap_ready:boolean;mschap_ready:boolean};services:Service[];groups:{id:number;name:string}[];runtime_verified:boolean};
const reasons:Record<string,string>={identity_disabled:'Учётная запись заблокирована',identity_expired:'Срок действия истёк',service_not_assigned:'Сервис не назначен',service_disabled:'Сервис отключён',credential_missing:'Нет подходящих реквизитов',no_effective_nas:'Нет эффективного NAS',nas_or_policy_ineligible:'NAS или политика не соответствует'};
export default function IdentityAaaPolicy({request,id}:{request:Request;id:number}){
 const [nas,setNas]=useState('all');
 const n=useData<Nas[]>(request,'nas');
 const d=useData<Policy>(request,'identities/'+id+'/aaa-policy'+(nas==='all'?'':'?nas_id='+encodeURIComponent(nas)));
 return <Space direction="vertical" className="full">
 <Alert type="info" message="Анализ конфигурации, не результат Access-Accept. Реальная авторизация зависит от запроса, протокола, реквизитов и состояния FreeRADIUS. Группы AD пока не предоставляют права автоматически."/>
 <Fault error={d.error||n.error}/>
 <Space wrap><Select value={nas} onChange={v=>setNas(String(v))} options={[{value:'all',label:'Все NAS'},...(n.data??[]).map(x=>({value:String(x.id),label:x.shortname}))]}/><Button onClick={d.refresh}>Обновить</Button></Space>
 {d.data&&<Space wrap><Tag color={d.data.identity.enabled?'green':'red'}>{d.data.identity.enabled?'Identity активна':'Identity заблокирована'}</Tag><Tag>PAP: {d.data.identity.pap_ready?'готов':'нет'}</Tag><Tag>MS-CHAP: {d.data.identity.mschap_ready?'готов':'нет'}</Tag></Space>}
 <Table<Service> rowKey="service" loading={d.loading} dataSource={d.data?.services??[]} columns={[
 {title:'Сервис',dataIndex:'service'},
 {title:'Статус',render:(_,r)=><Tag color={r.status==='configured'?'green':'red'}>{r.status==='configured'?'Настроен':'Ограничен'}</Tag>},
 {title:'Причины',render:(_,r)=>r.reasons.map(x=>reasons[x]??x).join('; ')||'—'},
 {title:'NAS / источник',render:(_,r)=><Space wrap>{r.targets.map(t=><Tag key={t.nas_id+'-'+t.source} color={t.eligible?'green':'red'}>{t.shortname}: {t.source}</Tag>)}</Space>}
 ]}/>
 {d.data&&<span>Локальные группы: {d.data.groups.map(g=>g.name).join(', ')||'—'}</span>}
 </Space>
}
