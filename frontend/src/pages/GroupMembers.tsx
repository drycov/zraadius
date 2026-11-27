import {useState} from 'react';
import {Alert,Button,Input,Select,Space,Table,Tag} from '../ui';
import {useData,Fault} from '../hooks';
import type {Request} from '../api';
type Identity={id:number;username:string;full_name:string;department:string;account_type:'person'|'service';enabled:boolean};
type Page={items:Identity[];next_after_id:number|null};
type Change={id:number;username:string;operation:'add'|'remove'};
export default function GroupMembers({request,id,onChanged}:{request:Request;id:number;onChanged:()=>void}){
 const path='identities/groups/'+id+'/members';
 const [cursors,setCursors]=useState([0]);
 const [query,setQuery]=useState('');
 const [search,setSearch]=useState('');
 const [offset,setOffset]=useState(0);
 const [target,setTarget]=useState('none');
 const [change,setChange]=useState<Change>();
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState('');
 const d=useData<Page>(request,path+'?limit=50&after_id='+cursors[cursors.length-1]);
 const candidates=useData<Identity[]>(request,'identities?limit=101&offset='+offset+'&q='+encodeURIComponent(search));
 const selected=candidates.data?.slice(0,100).find(x=>String(x.id)===target);
 const locked=busy||!!change;
 const apply=async()=>{if(!change||busy)return;setBusy(true);setError('');try{await request(path,'PATCH',{add:change.operation==='add'?[change.id]:[],remove:change.operation==='remove'?[change.id]:[],confirm:true});setChange(undefined);setTarget('none');d.refresh();onChanged()}catch(e){setError(e instanceof Error?e.message:'Ошибка изменения состава')}finally{setBusy(false)}};
 return <Space direction="vertical" className="full"><Alert type="info" message="Персональные и сервисные УЗ используют единый состав группы. Изменение членства влияет на наследуемые права, но не завершает активные сессии."/><Fault error={d.error||candidates.error||error}/>
 <strong>Добавить участника</strong><Space wrap><Input disabled={locked} value={query} maxLength={200} placeholder="Логин, ФИО, подразделение" onChange={e=>setQuery(e.target.value)}/><Button disabled={locked} onClick={()=>{setSearch(query.trim());setOffset(0);setTarget('none')}}>Найти</Button><Button disabled={locked||offset===0||candidates.loading} onClick={()=>{setOffset(x=>Math.max(0,x-100));setTarget('none')}}>Назад</Button><Button disabled={locked||candidates.loading||(candidates.data?.length??0)<=100} onClick={()=>{setOffset(x=>x+100);setTarget('none')}}>Далее</Button></Space>
 <Space wrap><Select disabled={locked||candidates.loading} value={target} onChange={v=>setTarget(String(v))} options={[{value:'none',label:'Выберите УЗ'},...(candidates.data??[]).slice(0,100).map(x=>({value:String(x.id),label:x.username+' · '+(x.account_type==='service'?'Сервисная':'Персональная')}))]}/><Button type="primary" disabled={locked||!selected} onClick={()=>{if(selected)setChange({id:selected.id,username:selected.username,operation:'add'})}}>Добавить</Button></Space>
 <strong>Участники группы</strong><Table<Identity> rowKey="id" loading={d.loading} pagination={false} dataSource={d.data?.items??[]} columns={[{title:'Логин',dataIndex:'username'},{title:'ФИО',dataIndex:'full_name'},{title:'Подразделение',dataIndex:'department'},{title:'Тип',render:(_,r)=>r.account_type==='service'?'Сервисная':'Персональная'},{title:'Состояние',render:(_,r)=><Tag color={r.enabled?'green':'red'}>{r.enabled?'Активна':'Заблокирована'}</Tag>},{title:'Действия',render:(_,r)=><Button danger disabled={locked} onClick={()=>setChange({id:r.id,username:r.username,operation:'remove'})}>Исключить</Button>}]}/>
 <Space wrap><Button disabled={locked||d.loading||cursors.length===1} onClick={()=>setCursors(x=>x.slice(0,-1))}>Назад</Button><span>Страница {cursors.length}</span><Button disabled={locked||d.loading||d.data?.next_after_id==null} onClick={()=>{const next=d.data?.next_after_id;if(next!=null)setCursors(x=>[...x,next])}}>Далее</Button><Button disabled={locked} onClick={d.refresh}>Обновить</Button></Space>
 {change&&<><Alert type="warning" message={(change.operation==='add'?'Добавление ':'Исключение ')+change.username+' изменяет наследуемые права. Подтвердите операцию.'}/><Space><Button type="primary" loading={busy} disabled={busy} onClick={()=>void apply()}>Подтвердить</Button><Button disabled={busy} onClick={()=>setChange(undefined)}>Отмена</Button></Space></>}
 </Space>
}
