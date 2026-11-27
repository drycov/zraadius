import React,{useEffect,useMemo,useState} from 'react';
import {Alert,App,Button,Card,Checkbox,Col,Form,Input,InputNumber,Modal,Popconfirm,Row,Select,Space,Table,Tag,Typography} from '../ui';
import {ReloadOutlined} from '../ui/icons';
import {type Request,type User,type Group,type Nas,type Session,type Audit,type Dashboard,type Attribute} from '../api';
import {StatCard} from '../vendor/design-kit/components/StatCard';
import MfaPanel from '../MfaPanel';
import {enc,useData,useAction,Fault} from '../hooks';
const {Text}=Typography;
function LegacyNetworkPolicy({request}:{request:Request}){
 const g=useData<Group[]>(request,'groups');const [group,setGroup]=useState('');const [form]=Form.useForm();const [busy,setBusy]=useState(false);const [loaded,setLoaded]=useState(false);const {message}=App.useApp();
 return <Space direction="vertical" className="full"><Fault error={g.error}/><Alert type="warning" message="Сетевые атрибуты применяются SQL-модулем ко всей группе. VLAN и Simultaneous-Use требуют проверки NAS; Device AAA пока закрыт."/><Card title="Network Policy"><Space><Select style={{minWidth:220}} placeholder="Группа" value={group||undefined} disabled={busy} options={(g.data??[]).map(x=>({label:x.name,value:x.name}))} onChange={v=>{setGroup(v);setLoaded(false);form.resetFields()}}/><Button disabled={!group||busy} onClick={async()=>{setBusy(true);setLoaded(false);try{const r=await request<{reply:Record<string,string>;control:Record<string,string>}>('groups/'+enc(group)+'/network-policy');form.setFieldsValue({vlan_id:r.reply['Tunnel-Private-Group-Id']?Number(r.reply['Tunnel-Private-Group-Id']):null,session_timeout:r.reply['Session-Timeout']?Number(r.reply['Session-Timeout']):null,simultaneous_use:r.control['Simultaneous-Use']?Number(r.control['Simultaneous-Use']):null});setLoaded(true)}catch(e){message.error(String(e))}finally{setBusy(false)}}}>Загрузить</Button></Space><Form form={form} layout="vertical" disabled={!loaded||busy} style={{marginTop:16}} onFinish={async v=>{setBusy(true);try{await request('groups/'+enc(group)+'/network-policy','PUT',v);message.success('Политика сохранена')}catch(e){message.error(String(e))}finally{setBusy(false)}}}><Form.Item name="vlan_id" label="Dynamic VLAN"><InputNumber min={1} max={4094}/></Form.Item><Form.Item name="session_timeout" label="Session timeout (seconds)"><InputNumber min={1} max={604800}/></Form.Item><Form.Item name="simultaneous_use" label="Simultaneous-Use"><InputNumber min={1} max={100}/></Form.Item><Button htmlType="submit" type="primary" loading={busy}>Сохранить</Button></Form></Card></Space>
}

import Tabs from '../ui/Tabs';
import {PolicyRuleEditor,type Rule} from './CentralizedPolicyRules';
import AccessTemplates from './AccessTemplates';
import PolicyCompliance from './PolicyCompliance';
type Registry={items:Rule[];next_after_id:number|null};
type IdentityChoice={id:number;username:string;account_type:'person'|'service'};
function RegistryView({request}:{request:Request}){
 const [filter,setFilter]=useState('all');
 const [cursors,setCursors]=useState<number[]>([0]);
 const [subject,setSubject]=useState<'identity'|'group'>('identity');
 const [target,setTarget]=useState('none');
 const [query,setQuery]=useState('');
 const [search,setSearch]=useState('');
 const [offset,setOffset]=useState(0);
 const [editing,setEditing]=useState<Rule|null|undefined>();
 const [removing,setRemoving]=useState<Rule>();
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState('');
 const d=useData<Registry>(request,'identities/policy-rules?limit=100&after_id='+cursors[cursors.length-1]+(filter==='all'?'':'&subject='+filter));
 const n=useData<Nas[]>(request,'nas');
 const g=useData<{id:number;name:string}[]>(request,'identities/groups');
 const i=useData<IdentityChoice[]>(request,'identities?limit=101&offset='+offset+'&q='+encodeURIComponent(search));
 const path=(r:Rule)=>'identities/'+(r.subject==='group'?'groups/'+r.group_id:r.identity_id)+'/policy-rules';
 const valid=subject==='group'?!!g.data?.some(x=>String(x.id)===target):!!i.data?.slice(0,100).some(x=>String(x.id)===target);
 const locked=editing!==undefined||!!removing||busy;
 const refresh=()=>{d.refresh();g.refresh();n.refresh();i.refresh()};
 const remove=async()=>{if(!removing||busy)return;setBusy(true);setError('');try{await request(path(removing)+'/'+removing.id,'DELETE');setRemoving(undefined);d.refresh()}catch(e){setError(e instanceof Error?e.message:'Ошибка удаления')}finally{setBusy(false)}};
 return <Space direction="vertical" className="full">
 <Alert type="warning" message="Единый реестр ALLOW/DENY. Активный DENY имеет приоритет, ALLOW не создаёт сервисное назначение. Действующие сессии автоматически не завершаются."/>
 <Fault error={d.error||n.error||g.error||i.error||error}/>
 <Card title="Создание политики"><Space direction="vertical" className="full">
 <Select disabled={locked} value={subject} options={[{value:'identity',label:'Учётная запись'},{value:'group',label:'Глобальная группа'}]} onChange={v=>{setSubject(String(v) as 'identity'|'group');setTarget('none')}}/>
 {subject==='identity'&&<Space wrap><Input disabled={locked} value={query} maxLength={200} placeholder="Поиск логина" onChange={e=>setQuery(e.target.value)}/><Button disabled={locked} onClick={()=>{setSearch(query.trim());setOffset(0);setTarget('none')}}>Найти</Button><Button disabled={locked||offset===0||i.loading} onClick={()=>{setOffset(v=>Math.max(0,v-100));setTarget('none')}}>Назад</Button><Button disabled={locked||i.loading||(i.data?.length??0)<=100} onClick={()=>{setOffset(v=>v+100);setTarget('none')}}>Далее</Button></Space>}
 <Select disabled={locked} value={target} onChange={v=>setTarget(String(v))} options={[{value:'none',label:'Выберите субъект'},...(subject==='group'?(g.data??[]).map(x=>({value:String(x.id),label:x.name})):(i.data??[]).slice(0,100).map(x=>({value:String(x.id),label:x.username+' · '+x.account_type})))]}/>
 <Button type="primary" disabled={!valid||locked||n.loading||!n.data} onClick={()=>setEditing(null)}>Создать политику</Button>
 </Space></Card>
 {editing!==undefined&&n.data&&<Card title="Редактор политики"><PolicyRuleEditor key={editing?.id??'new'} request={request} path={editing?path(editing):'identities/'+(subject==='group'?'groups/':'')+target+'/policy-rules'} nases={n.data} initial={editing} onClose={()=>setEditing(undefined)} onSaved={()=>{setEditing(undefined);d.refresh()}}/></Card>}
 <Card title="Единый реестр"><Space direction="vertical" className="full"><Space wrap><Select disabled={locked} value={filter} onChange={v=>{setFilter(String(v));setCursors([0])}} options={[{value:'all',label:'Все субъекты'},{value:'identity',label:'Учётные записи'},{value:'group',label:'Группы'}]}/><Button disabled={locked} onClick={refresh}>Обновить</Button></Space>
 <Table<Rule> rowKey="id" loading={d.loading} pagination={false} dataSource={d.data?.items??[]} columns={[{title:'Субъект',render:(_,r)=>r.subject_name??'—'},{title:'Тип',dataIndex:'subject'},{title:'Effect',render:(_,r)=><Tag color={r.effect==='DENY'?'red':'green'}>{r.effect}</Tag>},{title:'Услуга',render:(_,r)=>r.service??'Все'},{title:'NAS',render:(_,r)=>r.nas_id===null?'Все':n.data?.find(x=>x.id===r.nas_id)?.shortname??('#'+r.nas_id)},{title:'Активно',render:(_,r)=>r.enabled?'Да':'Нет'},{title:'Причина',dataIndex:'reason'},{title:'Действия',render:(_,r)=><Space wrap><Button disabled={locked||!n.data} onClick={()=>setEditing(r)}>Изменить</Button><Button disabled={locked} onClick={()=>setRemoving(r)}>Удалить</Button></Space>}]}/>
 <Space><Button disabled={locked||d.loading||cursors.length===1} onClick={()=>setCursors(v=>v.slice(0,-1))}>Назад</Button><span>Страница {cursors.length}</span><Button disabled={locked||d.loading||d.data?.next_after_id==null} onClick={()=>{const next=d.data?.next_after_id;if(next!=null)setCursors(v=>[...v,next])}}>Далее</Button></Space>
 {removing&&<><Alert type="warning" message={'Удаление политики #'+removing.id+' для '+removing.subject_name+' может изменить сетевой доступ.'}/><Space><Button type="primary" loading={busy} disabled={busy} onClick={()=>void remove()}>Подтвердить удаление</Button><Button disabled={busy} onClick={()=>setRemoving(undefined)}>Отмена</Button></Space></>}
 </Space></Card></Space>
}
export default function PolicyPage({request}:{request:Request}){
 return <Tabs label="Единый центр политик" items={[{id:'registry',label:'Правила доступа',content:<RegistryView request={request}/>},{id:'profiles',label:'Профили доступа',content:<AccessTemplates request={request} refresh={()=>{}}/>},{id:'compliance',label:'Соответствие',content:<PolicyCompliance request={request}/>},{id:'legacy',label:'Legacy RADIUS атрибуты',content:<LegacyNetworkPolicy request={request}/>} ]}/>
}
