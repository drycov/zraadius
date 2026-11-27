import {useState} from 'react';
import {Alert,Button,Checkbox,Space,Table,Tag} from '../ui';
import {useData,Fault} from '../hooks';
import type {Request} from '../api';
type Operation={service:string;action:'CREATE'|'UPDATE'|'DISABLE'|'KEEP';reason:string;expected_parameters:unknown;differences:{parameter:string;expected:unknown;actual:unknown;status:string}[];requires_review:boolean;apply_supported:boolean};
type Plan={source:string;effective_template_id:number|null;status:'blocked'|'in_sync'|'review_required';reason:string|null;operations:Operation[];runtime_changed:boolean};
const labels:Record<string,string>={individual_assignment_requires_review:'Индивидуальное назначение требует проверки',missing_service_parameters:'Не заданы параметры услуги',missing_or_disabled_assignment:'Назначение отсутствует или отключено',individual_parameters_require_review:'Индивидуальные параметры требуют проверки',no_detected_difference:'Расхождения не обнаружены',conflict:'Конфликт групповых профилей',none:'Профиль отсутствует',invalid_direct:'Прямой профиль недоступен',invalid_group:'Групповой профиль недоступен',direct:'Прямой профиль',group:'Групповой профиль'};
const display=(v:unknown)=>v===null||v===undefined?'—':typeof v==='object'?JSON.stringify(v):String(v);
export default function IdentityReconciliation({request,id}:{request:Request;id:number}){
 const d=useData<Plan>(request,'identities/'+id+'/profile-reconciliation');
 const [onlyChanges,setOnlyChanges]=useState(true);
 const plan=d.data;
 return <Space direction="vertical" className="full">
 <Alert type="info" message="Диагностический план. CREATE, UPDATE и DISABLE требуют отдельного административного решения. Применение операций не поддерживается."/>
 <Fault error={d.error}/>
 <Space wrap><Button disabled={d.loading} onClick={d.refresh}>Пересчитать план</Button><Checkbox checked={onlyChanges} onChange={e=>setOnlyChanges(e.target.checked)}>Только изменения</Checkbox></Space>
 {plan&&<><Space wrap><Tag color={plan.status==='blocked'?'red':plan.status==='in_sync'?'green':'orange'}>{plan.status==='blocked'?'Заблокирован':plan.status==='in_sync'?'Расхождения не обнаружены':'Требуется проверка'}</Tag><span>{labels[plan.source]??plan.source} {plan.effective_template_id===null?'':'#'+plan.effective_template_id}</span></Space>
 {plan.reason&&<Alert type="warning" message={labels[plan.reason]??plan.reason}/>}
 <Space wrap>{(['CREATE','UPDATE','DISABLE','KEEP'] as const).map(action=><Tag key={action}>{action}: {plan.operations.filter(o=>o.action===action).length}</Tag>)}</Space></>}
 <Table<Operation> rowKey="service" pagination={false} loading={d.loading} dataSource={(plan?.operations??[]).filter(o=>!onlyChanges||o.requires_review)} columns={[
 {title:'Услуга',dataIndex:'service'},
 {title:'Операция',render:(_,r)=><Tag color={r.action==='DISABLE'?'red':r.action==='UPDATE'?'orange':r.action==='CREATE'?'blue':'green'}>{r.action}</Tag>},
 {title:'Причина',render:(_,r)=>labels[r.reason]??r.reason},
 {title:'Параметры профиля',render:(_,r)=><code>{display(r.expected_parameters)}</code>},
 {title:'Расхождения',render:(_,r)=><Space direction="vertical">{r.differences.map(p=><span key={p.parameter}>{p.parameter}: {display(p.actual)} → {display(p.expected)}</span>)}</Space>},
 {title:'Применение',render:(_,r)=>r.requires_review?'Требует решения':'Не требуется'}
 ]}/>
 </Space>
}
