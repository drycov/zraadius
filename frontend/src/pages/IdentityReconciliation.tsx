import {useState} from 'react';
import {Alert,Button,Checkbox,Input,Select,Space,Table,Tag} from '../ui';
import {useData,useAction,Fault} from '../hooks';
import {ApiError,type Request} from '../api';
type Override={service:string;mode:'OVERRIDE'|'LOCKED'|'EXCLUDED';reason:string;updated_at:string};
const services=['device-aaa','l2tp','pppoe','hotspot','dot1x','wpa-enterprise','console'];
type Operation={override?:Pick<Override,'mode'|'reason'>|null;proposed_action?:string;service:string;action:'CREATE'|'UPDATE'|'DISABLE'|'KEEP';reason:string;expected_parameters:unknown;differences:{parameter:string;expected:unknown;actual:unknown;status:string}[];requires_review:boolean;apply_supported:boolean};
type Plan={revision:string;source:string;effective_template_id:number|null;status:'blocked'|'in_sync'|'review_required'|'protected';reason:string|null;operations:Operation[];runtime_changed:boolean};
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
 const [selection,setSelection]=useState<{revision:string;services:string[]}>({revision:'',services:[]});
 const [confirmed,setConfirmed]=useState(false);
 const [busy,setBusy]=useState(false);
 const [applyError,setApplyError]=useState('');
 const [applied,setApplied]=useState(false);
 const eligible=(plan?.operations??[]).filter(o=>o.apply_supported&&!o.override);
 const chosen=selection.revision===plan?.revision?selection.services.filter(s=>eligible.some(o=>o.service===s)):[];
 const clear=()=>{setSelection({revision:'',services:[]});setConfirmed(false)};
 const reload=()=>{clear();d.refresh();overrides.refresh()};
 const choose=(service:string,checked:boolean)=>{if(!plan)return;setSelection({revision:plan.revision,services:checked?[...new Set([...chosen,service])]:chosen.filter(s=>s!==service)});setConfirmed(false);setApplied(false)};
 const apply=async()=>{if(!plan||!confirmed||!chosen.length||busy||d.loading)return;setBusy(true);setApplyError('');setApplied(false);try{await request('identities/'+id+'/profile-reconciliation/apply','POST',{revision:plan.revision,services:chosen,confirm:true});setApplied(true);reload()}catch(e){setApplyError(e instanceof ApiError&&e.status===409?'Конфигурация изменилась. План пересчитан; проверьте операции повторно.':e instanceof Error?e.message:'Ошибка применения');reload()}finally{setBusy(false)}};
 return <Space direction="vertical" className="full">
 <Alert type="info" message="Выберите разрешённые операции CREATE / UPDATE. DISABLE и создание отсутствующих Device AAA, L2TP и Console требуют ручного решения. Изменение Console отзывает веб-сессии. Активные сессии автоматически не завершаются."/>
 <Fault error={d.error||overrides.error||applyError}/>{applied&&<Alert type="success" message="Выбранные операции применены. План обновляется."/>}
 <strong>Индивидуальные исключения</strong><Select disabled={busy} value={selected} options={services.map(v=>({value:v,label:v}))} onChange={v=>setSelected(String(v))}/>
 {!busy&&overrides.data&&<OverrideEditor key={selected+'-'+(overrides.data.find(r=>r.service===selected)?.updated_at??'inherit')} request={request} id={id} service={selected} current={overrides.data.find(r=>r.service===selected)} refresh={reload}/>}
 <Table<Override> rowKey="service" pagination={false} dataSource={overrides.data??[]} loading={overrides.loading} columns={[{title:'Услуга',dataIndex:'service'},{title:'Режим',dataIndex:'mode'},{title:'Обоснование',dataIndex:'reason'},{title:'Изменено',render:(_,r)=>new Date(r.updated_at).toLocaleString()}]}/>
 <Space wrap><Button disabled={d.loading||busy} onClick={()=>{setApplyError('');setApplied(false);reload()}}>Пересчитать план</Button><Checkbox checked={onlyChanges} onChange={e=>setOnlyChanges(e.target.checked)}>Только изменения</Checkbox></Space>
 {plan&&<><Space wrap><Tag color={plan.status==='blocked'?'red':plan.status==='in_sync'?'green':'orange'}>{plan.status==='blocked'?'Заблокирован':plan.status==='in_sync'?'Расхождения не обнаружены':plan.status==='protected'?'Расхождения защищены':'Требуется проверка'}</Tag><span>{labels[plan.source]??plan.source} {plan.effective_template_id===null?'':'#'+plan.effective_template_id}</span></Space>
 {plan.reason&&<Alert type="warning" message={labels[plan.reason]??plan.reason}/>}
 <Space wrap>{(['CREATE','UPDATE','DISABLE','KEEP'] as const).map(action=><Tag key={action}>{action}: {plan.operations.filter(o=>o.action===action).length}</Tag>)}</Space></>}
 <Table<Operation> rowKey="service" pagination={false} loading={d.loading} dataSource={(plan?.operations??[]).filter(o=>!onlyChanges||o.requires_review||!!o.override)} columns={[
 {title:'Выбор',render:(_,r)=><Checkbox checked={chosen.includes(r.service)} disabled={busy||d.loading||!r.apply_supported||!!r.override} onChange={e=>choose(r.service,e.target.checked)}/>},
 {title:'Услуга',dataIndex:'service'},
 {title:'Операция',render:(_,r)=><Tag color={r.action==='DISABLE'?'red':r.action==='UPDATE'?'orange':r.action==='CREATE'?'blue':'green'}>{r.action}</Tag>},
 {title:'Причина',render:(_,r)=>labels[r.reason]??r.reason},{title:'Защита',render:(_,r)=>r.override?<Space direction="vertical"><Tag color="orange">{r.override.mode}</Tag><span>{r.override.reason}</span><span>Предложено: {r.proposed_action}</span></Space>:'—'},
 {title:'Параметры профиля',render:(_,r)=><code>{display(r.expected_parameters)}</code>},
 {title:'Расхождения',render:(_,r)=><Space direction="vertical">{r.differences.map(p=><span key={p.parameter}>{p.parameter}: {display(p.actual)} → {display(p.expected)}</span>)}</Space>},
 {title:'Применение',render:(_,r)=>r.override?'Защищено':r.apply_supported?'Доступно':r.requires_review?'Вручную':'Не требуется'}
 ]}/>
 {eligible.length>0&&<Space direction="vertical" className="full"><Space wrap><Button disabled={busy||d.loading} onClick={()=>{if(plan){setSelection({revision:plan.revision,services:eligible.map(o=>o.service)});setConfirmed(false)}}}>Выбрать доступные</Button><Button disabled={busy} onClick={clear}>Снять выбор</Button><Tag>Выбрано: {chosen.length}</Tag></Space>
 <Checkbox checked={confirmed&&chosen.length>0} disabled={busy||d.loading||!chosen.length} onChange={e=>setConfirmed(e.target.checked)}>Проверил изменения и подтверждаю применение выбранных сетевых назначений</Checkbox>
 <Button type="primary" loading={busy} disabled={busy||d.loading||!confirmed||!chosen.length||!plan?.revision} onClick={()=>void apply()}>Применить выбранные операции</Button></Space>}
 </Space>
}
