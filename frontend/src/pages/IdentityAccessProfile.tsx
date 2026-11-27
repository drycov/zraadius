import {useState} from 'react';
import {Alert,Button,Select,Space,Table,Tag} from '../ui';
import {useData,useAction,Fault} from '../hooks';
import {serviceCodes,type AccessTemplate} from './AccessTemplates';
import type {Request} from '../api';
type ParameterComparison={service:string;parameter:string;expected:unknown;actual:unknown;status:'match'|'different'|'missing'};
const parameterLabels:Record<string,string>={nas_id:'NAS',role:'Роль',filter_id:'Filter-Id',profile_id:'Профиль',rate_limit:'Rate Limit',pool:'IP Pool',interim_seconds:'Interim Interval',session_seconds:'Session Timeout',idle_seconds:'Idle Timeout',vlan_id:'VLAN ID',additional_direct_nas:'Дополнительные NAS'};
const formatValue=(v:unknown)=>v===null||v===undefined?'—':Array.isArray(v)?(v.length?v.join(', '):'Нет'):String(v);
type Comparison={assigned_template_id:number|null;template:Pick<AccessTemplate,'id'|'name'|'enabled'|'account_type'>|null;actual_services:string[];expected_services:string[];missing_services:string[];extra_services:string[];runtime_changed:boolean;parameter_comparison?:ParameterComparison[]};
type GroupCandidate={group_id:number;group_name:string;template_id:number;template_name:string;enabled:boolean;account_type:'person'|'service'};
type EffectiveProfile={source:'direct'|'group'|'conflict'|'invalid_direct'|'invalid_group'|'none';effective_template_id:number|null;group_candidates:GroupCandidate[];comparison:Comparison;runtime_changed:boolean};
const sourceLabels:Record<EffectiveProfile['source'],string>={direct:'Прямое назначение',group:'Наследование от группы',conflict:'Конфликт групповых профилей',invalid_direct:'Прямой профиль недоступен',invalid_group:'Групповой профиль недоступен',none:'Профиль отсутствует'};
function EffectiveProfileView({data,kind}:{data:EffectiveProfile;kind:'person'|'service'}){
 const conflict=['conflict','invalid_direct','invalid_group'].includes(data.source);
 const comparison=data.comparison;
 return <Space direction="vertical" className="full">
 <strong>Результирующий профиль</strong>
 <Space wrap><Tag color={conflict?'red':data.source==='none'?'orange':'green'}>{sourceLabels[data.source]}</Tag><span>{comparison.template?.name??'Не определён'}</span></Space>
 {conflict&&<Alert type="warning" message="Наследуемый профиль не выбран. Проверьте групповые привязки или назначьте совместимый прямой профиль. Действующие сетевые права не изменены."/>}
 <Table<GroupCandidate> rowKey="group_id" pagination={false} dataSource={data.group_candidates} columns={[{title:'Группа',dataIndex:'group_name'},{title:'Профиль',dataIndex:'template_name'},{title:'Состояние',render:(_,r)=><Tag color={r.enabled&&r.account_type===kind?'green':'red'}>{r.enabled&&r.account_type===kind?'Доступен':'Недоступен'}</Tag>},{title:'Выбран',render:(_,r)=>data.source==='group'&&r.template_id===data.effective_template_id?'Да':'—'}]}/>
 {comparison.template&&<><span>Отсутствующие услуги: {comparison.missing_services.join(', ')||'—'}</span><span>Дополнительные услуги: {comparison.extra_services.join(', ')||'—'}</span><Table<ParameterComparison> rowKey={r=>r.service+'-'+r.parameter} pagination={false} dataSource={(comparison.parameter_comparison??[]).filter(r=>r.status!=='match')} columns={[{title:'Сервис',dataIndex:'service'},{title:'Параметр',render:(_,r)=>parameterLabels[r.parameter]??r.parameter},{title:'Ожидается',render:(_,r)=>formatValue(r.expected)},{title:'Фактически',render:(_,r)=>formatValue(r.actual)},{title:'Статус',render:(_,r)=><Tag color="orange">{r.status==='missing'?'Отсутствует':'Отличается'}</Tag>}]}/></>}
 <Alert type="info" message="Результирующий профиль является диагностическим. Наследование профиля не выдаёт и не отзывает сетевой доступ."/>
 </Space>
}
export default function IdentityAccessProfile({request,id,kind,onSaved}:{request:Request;id:number;kind:'person'|'service';onSaved:(id:number|null)=>void}){
 const path='identities/'+id+'/access-profile';
 const d=useData<Comparison>(request,path);
 const effective=useData<EffectiveProfile>(request,'identities/'+id+'/effective-access-profile');
 const templates=useData<AccessTemplate[]>(request,'identities/access-templates');
 const [selection,setSelection]=useState<string>();
 const [preview,setPreview]=useState<Comparison>();
 const a=useAction(()=>{d.refresh();effective.refresh();setPreview(undefined);setSelection(undefined)});
 const [previewBusy,setPreviewBusy]=useState(false);
 const [previewError,setPreviewError]=useState('');
 const busy=a.busy||previewBusy;
 const current=d.data;
 const selected=selection??String(current?.assigned_template_id??'none');
 const target=selected==='none'?null:Number(selected);
 const options=[{value:'none',label:'Без профиля'},...(templates.data??[]).filter(t=>t.enabled&&t.account_type===kind).map(t=>({value:String(t.id),label:t.name}))];
 if(current?.template&&!options.some(o=>o.value===String(current.template?.id)))options.push({value:String(current.template.id),label:current.template.name+' (недоступен)'});
 const valid=target===null||!!templates.data?.some(t=>t.id===target&&t.enabled&&t.account_type===kind);
 const comparison=preview??current;
 return <Space direction="vertical" className="full">
 <Alert type="info" message="Привязка профиля не изменяет сетевые права. Сравнение показывает включённые услуги, а не результат RADIUS-авторизации."/>
 <Fault error={d.error||templates.error||effective.error||previewError}/>
 <span>Прямой профиль: {current?.template?.name??'Не назначен'}</span>
 <Select value={selected} options={options} disabled={busy||d.loading||templates.loading} onChange={v=>{setSelection(String(v));setPreview(undefined);setPreviewError('')}}/>
 <Space wrap><Button disabled={busy||!current||!valid} onClick={async()=>{setPreviewBusy(true);setPreview(undefined);setPreviewError('');try{setPreview(await request<Comparison>(path,'PUT',{template_id:target,preview:true}))}catch(e){setPreviewError(e instanceof Error?e.message:'Ошибка предпросмотра')}finally{setPreviewBusy(false)}}}>Предпросмотр</Button><Button onClick={()=>{setPreview(undefined);setSelection(undefined);setPreviewError('');d.refresh();templates.refresh();effective.refresh()}} disabled={busy}>Обновить</Button></Space>
 {comparison&&<Table<{service:string;expected:boolean;actual:boolean}> rowKey="service" pagination={false} dataSource={serviceCodes.map(service=>({service,expected:comparison.expected_services.includes(service),actual:comparison.actual_services.includes(service)}))} columns={[{title:'Услуга',dataIndex:'service'},{title:'Профиль',render:(_,r)=>comparison.template?(r.expected?'Да':'Нет'):'—'},{title:'Фактически',render:(_,r)=>r.actual?'Да':'Нет'},{title:'Сравнение',render:(_,r)=>!comparison.template?'—':<Tag color={r.expected===r.actual?'green':'orange'}>{r.expected===r.actual?'Совпадает':r.expected?'Отсутствует':'Дополнительная'}</Tag>}]}/>}
 {comparison?.template&&<><strong>Сравнение параметров прямых назначений</strong><Alert type="info" message="Сравниваются явно заданные параметры включённых прямых назначений. Наследуемые групповые разрешения и результат авторизации не проверяются."/>
 <Space wrap><Tag color="green">Совпадают: {(comparison.parameter_comparison??[]).filter(r=>r.status==='match').length}</Tag><Tag color="orange">Расхождения: {(comparison.parameter_comparison??[]).filter(r=>r.status!=='match').length}</Tag></Space>
 <Table<ParameterComparison> rowKey={r=>r.service+'-'+r.parameter} pagination={false} dataSource={comparison.parameter_comparison??[]} columns={[{title:'Сервис',dataIndex:'service'},{title:'Параметр',render:(_,r)=>parameterLabels[r.parameter]??r.parameter},{title:'Профиль',render:(_,r)=>formatValue(r.expected)},{title:'Фактически',render:(_,r)=>formatValue(r.actual)},{title:'Статус',render:(_,r)=><Tag color={r.status==='match'?'green':r.status==='missing'?'red':'orange'}>{r.status==='match'?'Совпадает':r.status==='missing'?'Отсутствует':'Отличается'}</Tag>}]}/>
 </>}
 {effective.data&&<EffectiveProfileView data={effective.data} kind={kind}/>}
 {preview&&<><Alert type="warning" message="Сохранится только связь с профилем. Существующие назначения останутся без изменений."/><Button type="primary" disabled={busy||!valid} onClick={()=>a.run(async()=>{const result=await request<Comparison>(path,'PUT',{template_id:target,preview:false});onSaved(result.assigned_template_id)})}>Подтвердить привязку</Button></>}
 </Space>
}
