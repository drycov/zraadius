import {useState} from 'react';
import {Alert,Button,Select,Space,Table,Tag} from '../ui';
import {useData,useAction,Fault} from '../hooks';
import {serviceCodes,type AccessTemplate} from './AccessTemplates';
import type {Request} from '../api';
type Comparison={assigned_template_id:number|null;template:Pick<AccessTemplate,'id'|'name'|'enabled'|'account_type'>|null;actual_services:string[];expected_services:string[];missing_services:string[];extra_services:string[];runtime_changed:boolean};
export default function IdentityAccessProfile({request,id,kind,onSaved}:{request:Request;id:number;kind:'person'|'service';onSaved:(id:number|null)=>void}){
 const path='identities/'+id+'/access-profile';
 const d=useData<Comparison>(request,path);
 const templates=useData<AccessTemplate[]>(request,'identities/access-templates');
 const [selection,setSelection]=useState<string>();
 const [preview,setPreview]=useState<Comparison>();
 const a=useAction(()=>{d.refresh();setPreview(undefined);setSelection(undefined)});
 const current=d.data;
 const selected=selection??String(current?.assigned_template_id??'none');
 const target=selected==='none'?null:Number(selected);
 const options=[{value:'none',label:'Без профиля'},...(templates.data??[]).filter(t=>t.enabled&&t.account_type===kind).map(t=>({value:String(t.id),label:t.name}))];
 if(current?.template&&!options.some(o=>o.value===String(current.template?.id)))options.push({value:String(current.template.id),label:current.template.name+' (недоступен)'});
 const valid=target===null||!!templates.data?.some(t=>t.id===target&&t.enabled&&t.account_type===kind);
 const comparison=preview??current;
 return <Space direction="vertical" className="full">
 <Alert type="info" message="Привязка профиля не изменяет сетевые права. Сравнение показывает включённые услуги, а не результат RADIUS-авторизации."/>
 <Fault error={d.error||templates.error}/>
 <span>Текущий профиль: {current?.template?.name??'Не назначен'}</span>
 <Select value={selected} options={options} disabled={a.busy||d.loading||templates.loading} onChange={v=>{setSelection(String(v));setPreview(undefined)}}/>
 <Space wrap><Button disabled={a.busy||!current||!valid} onClick={()=>a.run(async()=>{setPreview(await request<Comparison>(path,'PUT',{template_id:target,preview:true}))})}>Предпросмотр</Button><Button onClick={()=>{setPreview(undefined);setSelection(undefined);d.refresh();templates.refresh()}} disabled={a.busy}>Обновить</Button></Space>
 {comparison&&<Table<{service:string;expected:boolean;actual:boolean}> rowKey="service" pagination={false} dataSource={serviceCodes.map(service=>({service,expected:comparison.expected_services.includes(service),actual:comparison.actual_services.includes(service)}))} columns={[{title:'Услуга',dataIndex:'service'},{title:'Профиль',render:(_,r)=>comparison.template?(r.expected?'Да':'Нет'):'—'},{title:'Фактически',render:(_,r)=>r.actual?'Да':'Нет'},{title:'Сравнение',render:(_,r)=>!comparison.template?'—':<Tag color={r.expected===r.actual?'green':'orange'}>{r.expected===r.actual?'Совпадает':r.expected?'Отсутствует':'Дополнительная'}</Tag>}]}/>}
 {preview&&<><Alert type="warning" message="Сохранится только связь с профилем. Существующие назначения останутся без изменений."/><Button type="primary" disabled={a.busy||!valid} onClick={()=>a.run(async()=>{const result=await request<Comparison>(path,'PUT',{template_id:target,preview:false});onSaved(result.assigned_template_id)})}>Подтвердить привязку</Button></>}
 </Space>
}
