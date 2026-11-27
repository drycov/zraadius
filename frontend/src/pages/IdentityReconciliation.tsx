import {useState} from 'react';
import {Alert,Button,Checkbox,Input,Select,Space,Table,Tag} from '../ui';
import {useData,useAction,Fault} from '../hooks';
import type {Request} from '../api';
type Override={service:string;mode:'OVERRIDE'|'LOCKED'|'EXCLUDED';reason:string;updated_at:string};
const services=['device-aaa','l2tp','pppoe','hotspot','dot1x','wpa-enterprise','console'];
type Operation={override?:Pick<Override,'mode'|'reason'>|null;proposed_action?:string;service:string;action:'CREATE'|'UPDATE'|'DISABLE'|'KEEP';reason:string;expected_parameters:unknown;differences:{parameter:string;expected:unknown;actual:unknown;status:string}[];requires_review:boolean;apply_supported:boolean};
type Plan={source:string;effective_template_id:number|null;status:'blocked'|'in_sync'|'review_required'|'protected';reason:string|null;operations:Operation[];runtime_changed:boolean};
const labels:Record<string,string>={protected_by_override:'Защищено индивидуальным исключением',individual_assignment_requires_review:'Индивидуальное назначение требует проверки',missing_service_parameters:'Не заданы параметры услуги',missing_or_disabled_assignment:'Назначение отсутствует или отключено',individual_parameters_require_review:'Индивидуальные параметры требуют проверки',no_detected_difference:'Расхождения не обнаружены',conflict:'Конфликт групповых профилей',none:'Профиль отсутствует',invalid_direct:'Прямой профиль недоступен',invalid_group:'Групповой профиль недоступен',direct:'Прямой профиль',group:'Групповой профиль'};
const display=(v:unknown)=>v===null||v===undefined?'—':typeof v==='object'?JSON.stringify(v):String(v);
function OverrideEditor({request,id,service,current,refresh}:{request:Request;id:number;service:string;current?:Override;refresh:()=>void}){
 const [mode,setMode]=useState<Override['mode']|'INHERIT'>(current?.mode??'INHERIT');
 const [reason,setReason]=useState('');
 const a=useAction(refresh);
 return <Space direction="vertical" className="full"><strong>{service}</strong><span>Текущий режим: {current?.mode??'INHERIT'}</span>{current&&<span>Обоснование: {current.reason}</span>}
 <Select value={mode} disabled={a.busy} options={['INHERIT','OVERRIDE','LOCKED','EXCLUDED'].map(v=>({value:v,label:v}))} onChange={v=>setMode(String(v) as Override['mode']|'INHERIT')}/>
 <Input value={reason} maxLength={500} disabled={a.busy} placeholder="Обоснование изменения" onChange={e=>setReason(e.target.value)}/>
 <Button disabled={a.busy||!reason.trim()} loading={a.busy} onClick={()=>a.run(()=>request('identities/'+id+'/profile-overrides/'+service,'PUT',{mode,reason:reason.trim()}))}>Сохранить режим</Button></Space>
}
export default function IdentityReconciliation({request,id}:{request:Request;id:number}){
 const d=useData<Plan>(request,'identities/'+id+'/profile-reconciliation');
 const overrides=useData<Override[]>(request,'identities/'+id+'/profile-overrides');
 const [selected,setSelected]=useState(services[0]);
 const [onlyChanges,setOnlyChanges]=useState(true);
 const plan=d.data;
 return <Space direction="vertical" className="full">
 <Alert type="info" message="Диагностический план. CREATE, UPDATE и DISABLE требуют отдельного административного решения. Применение операций не поддерживается."/>
 <Fault error={d.error||overrides.error}/>
 <strong>Индивидуальные исключения</strong><Select value={selected} options={services.map(v=>({value:v,label:v}))} onChange={v=>setSelected(String(v))}/>
 {overrides.data&&<OverrideEditor key={selected+'-'+(overrides.data.find(r=>r.service===selected)?.updated_at??'inherit')} request={request} id={id} service={selected} current={overrides.data.find(r=>r.service===selected)} refresh={()=>{overrides.refresh();d.refresh()}}/>}
 <Table<Override> rowKey="service" pagination={false} dataSource={overrides.data??[]} loading={overrides.loading} columns={[{title:'Услуга',dataIndex:'service'},{title:'Режим',dataIndex:'mode'},{title:'Обоснование',dataIndex:'reason'},{title:'Изменено',render:(_,r)=>new Date(r.updated_at).toLocaleString()}]}/>
 <Space wrap><Button disabled={d.loading} onClick={()=>{d.refresh();overrides.refresh()}}>Пересчитать план</Button><Checkbox checked={onlyChanges} onChange={e=>setOnlyChanges(e.target.checked)}>Только изменения</Checkbox></Space>
 {plan&&<><Space wrap><Tag color={plan.status==='blocked'?'red':plan.status==='in_sync'?'green':'orange'}>{plan.status==='blocked'?'Заблокирован':plan.status==='in_sync'?'Расхождения не обнаружены':plan.status==='protected'?'Расхождения защищены':'Требуется проверка'}</Tag><span>{labels[plan.source]??plan.source} {plan.effective_template_id===null?'':'#'+plan.effective_template_id}</span></Space>
 {plan.reason&&<Alert type="warning" message={labels[plan.reason]??plan.reason}/>}
 <Space wrap>{(['CREATE','UPDATE','DISABLE','KEEP'] as const).map(action=><Tag key={action}>{action}: {plan.operations.filter(o=>o.action===action).length}</Tag>)}</Space></>}
 <Table<Operation> rowKey="service" pagination={false} loading={d.loading} dataSource={(plan?.operations??[]).filter(o=>!onlyChanges||o.requires_review||!!o.override)} columns={[
 {title:'Услуга',dataIndex:'service'},
 {title:'Операция',render:(_,r)=><Tag color={r.action==='DISABLE'?'red':r.action==='UPDATE'?'orange':r.action==='CREATE'?'blue':'green'}>{r.action}</Tag>},
 {title:'Причина',render:(_,r)=>labels[r.reason]??r.reason},{title:'Защита',render:(_,r)=>r.override?<Space direction="vertical"><Tag color="orange">{r.override.mode}</Tag><span>{r.override.reason}</span><span>Предложено: {r.proposed_action}</span></Space>:'—'},
 {title:'Параметры профиля',render:(_,r)=><code>{display(r.expected_parameters)}</code>},
 {title:'Расхождения',render:(_,r)=><Space direction="vertical">{r.differences.map(p=><span key={p.parameter}>{p.parameter}: {display(p.actual)} → {display(p.expected)}</span>)}</Space>},
 {title:'Применение',render:(_,r)=>r.override?'Защищено':r.requires_review?'Требует решения':'Не требуется'}
 ]}/>
 </Space>
}
