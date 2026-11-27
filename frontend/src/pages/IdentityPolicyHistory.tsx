import {useState} from 'react';
import {Alert,Button,Checkbox,Space,Table,Tag} from '../ui';
import {useData,Fault} from '../hooks';
import type {Request} from '../api';
type Snapshot=Record<string,Record<string,unknown>|null>;
type Entry={id:number;identity_id:number;username:string;actor:string;operation:'apply'|'rollback';revision:string;before_state:Snapshot;after_state:Snapshot;rollback_of:number|null;created_at:string;rolled_back:boolean};
type History={items:Entry[];more:boolean};
const PAGE=25;
const display=(v:unknown)=>v===undefined||v===null?'—':typeof v==='boolean'?(v?'Включено':'Отключено'):typeof v==='object'?JSON.stringify(v):String(v);
type Difference={key:string;service:string;field:string;before:unknown;after:unknown};
function differences(entry:Entry):Difference[]{
 return [...new Set([...Object.keys(entry.before_state),...Object.keys(entry.after_state)])].sort().flatMap(service=>{
  const before=entry.before_state[service],after=entry.after_state[service];
  const fields=[...new Set([...Object.keys(before??{}),...Object.keys(after??{})])].sort();
  return [{key:service+':presence',service,field:'Назначение',before:before?'Существует':'Отсутствует',after:after?'Существует':'Отсутствует'},...fields.map(field=>({key:service+':'+field,service,field,before:before?.[field],after:after?.[field]}))];
 });
}
export default function IdentityPolicyHistory({request,id}:{request:Request;id:number}){
 const [offset,setOffset]=useState(0);
 const d=useData<History>(request,'identities/'+id+'/policy-history?limit='+PAGE+'&offset='+offset);
 const [selected,setSelected]=useState<number|null>(null);
 const [confirmed,setConfirmed]=useState(false);
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState('');
 const [success,setSuccess]=useState('');
 const entry=d.data?.items.find(r=>r.id===selected);
 const clear=()=>{setSelected(null);setConfirmed(false)};
 const refresh=()=>{clear();d.refresh()};
 const page=(value:number)=>{clear();setError('');setSuccess('');setOffset(value)};
 const rollback=async()=>{
  if(!entry||entry.rolled_back||entry.operation!=='apply'||!confirmed||busy||d.loading)return;
  setBusy(true);setError('');setSuccess('');
  try{
   const result=await request<{history_id:number}>('identities/'+id+'/policy-history/'+entry.id+'/rollback','POST',{confirm:true});
   setSuccess('Восстановление выполнено. Транзакция #'+result.history_id+'. Активные сессии не завершены.');
   setOffset(0);refresh();
  }catch(e){setError(e instanceof Error?e.message:'Ошибка восстановления');refresh()}
  finally{setBusy(false)}
 };
 return <Space direction="vertical" className="full">
 <Alert type="info" message="История содержит операции применения и восстановления профилей. Сервер проверяет текущие назначения, последующие транзакции и индивидуальные исключения перед rollback."/>
 <Fault error={d.error||error}/>{success&&<Alert type="success" message={success}/>}
 <Space wrap><Button disabled={busy||d.loading} onClick={()=>{setError('');setSuccess('');refresh()}}>Обновить</Button><Button disabled={busy||d.loading||offset===0} onClick={()=>page(Math.max(0,offset-PAGE))}>Назад</Button><span>Страница {Math.floor(offset/PAGE)+1}</span><Button disabled={busy||d.loading||!d.data?.more} onClick={()=>page(offset+PAGE)}>Далее</Button></Space>
 <Table<Entry> rowKey="id" pagination={false} loading={d.loading} dataSource={d.data?.items??[]} columns={[
 {title:'ID',dataIndex:'id'},{title:'Дата',render:(_,r)=>new Date(r.created_at).toLocaleString()},
 {title:'Администратор',dataIndex:'actor'},{title:'Операция',render:(_,r)=><Tag color={r.operation==='apply'?'blue':'orange'}>{r.operation==='apply'?'APPLY':'ROLLBACK'}</Tag>},
 {title:'Услуги',render:(_,r)=>Object.keys(r.after_state).join(', ')},
 {title:'Состояние',render:(_,r)=>r.rolled_back?'Отменена':r.operation==='rollback'?'Восстановление #'+r.rollback_of:'Применена'},
 {title:'Действия',render:(_,r)=><Button disabled={busy} onClick={()=>{setSelected(r.id);setConfirmed(false);setError('');setSuccess('')}}>Подробнее</Button>}
 ]}/>
 {entry&&<Space direction="vertical" className="full"><strong>Транзакция #{entry.id}</strong><span>Пользователь: {entry.username}</span><span>Ревизия: <code>{entry.revision}</code></span>
 <Table<Difference> rowKey="key" pagination={false} dataSource={differences(entry)} columns={[{title:'Услуга',dataIndex:'service'},{title:'Параметр',dataIndex:'field'},{title:'BEFORE',render:(_,r)=>display(r.before)},{title:'AFTER',render:(_,r)=>display(r.after)}]}/>
 {entry.operation==='apply'&&!entry.rolled_back&&<><Alert type="warning" message="Rollback восстановит все услуги этой транзакции. Если назначения, исключения или история изменились, сервер отклонит запрос. Активные сессии автоматически не завершаются."/><Checkbox checked={confirmed} disabled={busy} onChange={e=>setConfirmed(e.target.checked)}>Подтверждаю восстановление всей транзакции #{entry.id}</Checkbox><Button type="primary" disabled={!confirmed||busy||d.loading} loading={busy} onClick={()=>void rollback()}>Восстановить BEFORE</Button></>}
 <Button disabled={busy} onClick={clear}>Закрыть детали</Button></Space>}
 </Space>
}
