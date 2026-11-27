import {useState} from 'react';
import {Alert,Button,Checkbox,Input,Select,Space,Table,Tag} from '../ui';
import {useData,Fault} from '../hooks';
import type {Request,Nas} from '../api';
export type Rule={identity_id?:number|null;group_id?:number|null;subject_name?:string;subject?:'identity'|'group';id:number;service:string|null;nas_id:number|null;effect:'ALLOW'|'DENY';enabled:boolean;reason:string;source?:string;group_name?:string|null};
type Rules={items:Rule[]};
const services=['device-aaa','l2tp','pppoe','hotspot','dot1x','wpa-enterprise'];
export function PolicyRuleEditor({request,path,nases,initial,onClose,onSaved}:{request:Request;path:string;nases:Nas[];initial:Rule|null;onClose:()=>void;onSaved:()=>void}){
 const [service,setService]=useState(initial?.service??'all');
 const [nas,setNas]=useState(String(initial?.nas_id??'all'));
 const [effect,setEffect]=useState<'ALLOW'|'DENY'>(initial?.effect??'DENY');
 const [enabled,setEnabled]=useState(initial?.enabled??false);
 const [reason,setReason]=useState(initial?.reason??'');
 const [confirmed,setConfirmed]=useState(false);
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState('');
 const available=nases.filter(n=>service==='all'||!n.services||n.services.includes(service));
 const options=[{value:'all',label:'Все NAS'},...available.map(n=>({value:String(n.id),label:n.shortname+' ('+n.nasname+')'}))];
 if(!options.some(x=>x.value===nas))options.push({value:nas,label:'Недоступный NAS #'+nas});
 const valid=!!reason.trim()&&(nas==='all'||available.some(n=>String(n.id)===nas));
 const save=async()=>{if(!valid||!confirmed||busy)return;setBusy(true);setError('');try{await request(path+(initial?'/'+initial.id:''),initial?'PUT':'POST',{service:service==='all'?null:service,nas_id:nas==='all'?null:Number(nas),effect,enabled,reason:reason.trim()});onSaved()}catch(e){setError(e instanceof Error?e.message:'Ошибка сохранения')}finally{setBusy(false)}};
 return <Space direction="vertical" className="full"><strong>{initial?'Редактирование #'+initial.id:'Новое правило'}</strong><Fault error={error}/>
 <label>Действие<Select disabled={busy} value={effect} onChange={v=>{setEffect(String(v) as 'ALLOW'|'DENY');setConfirmed(false)}} options={['ALLOW','DENY'].map(v=>({value:v,label:v}))}/></label>
 <label>Услуга<Select disabled={busy} value={service} options={[{value:'all',label:'Все сетевые услуги'},...services.map(v=>({value:v,label:v}))]} onChange={v=>{setService(String(v));setConfirmed(false)}}/></label>
 <label>NAS<Select disabled={busy} value={nas} options={options} onChange={v=>{setNas(String(v));setConfirmed(false)}}/></label>
 <Checkbox disabled={busy} checked={enabled} onChange={e=>{setEnabled(e.target.checked);setConfirmed(false)}}>Правило активно</Checkbox>
 <Input disabled={busy} value={reason} maxLength={500} placeholder="Обоснование" onChange={e=>{setReason(e.target.value);setConfirmed(false)}}/>
 {effect==='DENY'&&enabled&&<Alert type="warning" message="Активный DENY может блокировать новые подключения в указанной области. Групповое правило затрагивает всех участников."/>}
 <Checkbox checked={confirmed} disabled={busy} onChange={e=>setConfirmed(e.target.checked)}>Подтверждаю изменение политики доступа</Checkbox>
 <Space wrap><Button type="primary" loading={busy} disabled={!valid||!confirmed||busy} onClick={()=>void save()}>Сохранить</Button><Button disabled={busy} onClick={onClose}>Отмена</Button></Space></Space>
}
function Inherited({request,id}:{request:Request;id:number}){
 const d=useData<Rules>(request,'identities/'+id+'/policy-rule-candidates');
 return <Space direction="vertical" className="full"><strong>Наследуемые правила</strong><Fault error={d.error}/><Button disabled={d.loading} onClick={d.refresh}>Обновить наследование</Button><Table<Rule> rowKey="id" loading={d.loading} pagination={false} dataSource={(d.data?.items??[]).filter(r=>r.source==='group')} columns={[{title:'Группа',dataIndex:'group_name'},{title:'Effect',dataIndex:'effect'},{title:'Услуга',render:(_,r)=>r.service??'Все'},{title:'NAS',render:(_,r)=>r.nas_id??'Все'},{title:'Активность',render:(_,r)=>r.enabled?'Да':'Нет'},{title:'Причина',dataIndex:'reason'}]}/></Space>
}
export default function CentralizedPolicyRules({request,id,subject='identity'}:{request:Request;id:number;subject?:'identity'|'group'}){
 const path='identities/'+(subject==='group'?'groups/':'')+id+'/policy-rules';
 const d=useData<Rules>(request,path);const n=useData<Nas[]>(request,'nas');
 const [editing,setEditing]=useState<Rule|null|undefined>();
 const [deleting,setDeleting]=useState<Rule>();
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState('');
 const remove=async()=>{if(!deleting||busy)return;setBusy(true);setError('');try{await request(path+'/'+deleting.id,'DELETE');setDeleting(undefined);d.refresh()}catch(e){setError(e instanceof Error?e.message:'Ошибка удаления')}finally{setBusy(false)}};
 return <Space direction="vertical" className="full"><Alert type="warning" message="DENY имеет приоритет над ALLOW. ALLOW не выдаёт доступ без существующего назначения и аутентификации. Применение DENY зависит от версии развёрнутого FreeRADIUS; активные сессии не завершаются автоматически."/><Fault error={d.error||n.error||error}/>
 <Space wrap><Button type="primary" disabled={busy||d.loading||n.loading||editing!==undefined||!!deleting} onClick={()=>setEditing(null)}>Создать правило</Button><Button disabled={busy||editing!==undefined||!!deleting} onClick={()=>{d.refresh();n.refresh()}}>Обновить</Button></Space>
 <Table<Rule> rowKey="id" loading={d.loading} pagination={false} dataSource={d.data?.items??[]} columns={[{title:'ID',dataIndex:'id'},{title:'Effect',render:(_,r)=><Tag color={r.effect==='DENY'?'red':'green'}>{r.effect}</Tag>},{title:'Услуга',render:(_,r)=>r.service??'Все'},{title:'NAS',render:(_,r)=>r.nas_id===null?'Все':n.data?.find(x=>x.id===r.nas_id)?.shortname??('#'+r.nas_id)},{title:'Состояние',render:(_,r)=>r.enabled?'Активно':'Отключено'},{title:'Причина',dataIndex:'reason'},{title:'Действия',render:(_,r)=><Space wrap><Button disabled={busy||editing!==undefined||!!deleting} onClick={()=>setEditing(r)}>Изменить</Button><Button disabled={busy||editing!==undefined||!!deleting} onClick={()=>setDeleting(r)}>Удалить</Button></Space>}]}/>
 {editing!==undefined&&n.data&&<PolicyRuleEditor key={editing?.id??'new'} request={request} path={path} nases={n.data} initial={editing} onClose={()=>setEditing(undefined)} onSaved={()=>{setEditing(undefined);d.refresh()}}/>}
 {deleting&&<Space direction="vertical"><Alert type="warning" message={'Удаление правила #'+deleting.id+' может изменить доступ к сети. Подтвердите операцию.'}/><Space wrap><Button type="primary" loading={busy} disabled={busy} onClick={()=>void remove()}>Подтвердить удаление</Button><Button disabled={busy} onClick={()=>setDeleting(undefined)}>Отмена</Button></Space></Space>}
 {subject==='identity'&&<Inherited request={request} id={id}/>}
 </Space>
}
