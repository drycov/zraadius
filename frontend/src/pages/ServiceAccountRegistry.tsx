import {useState} from 'react';
import {Alert,Button,Space,Table,Tag,Modal,Select} from '../ui';
import {useData,useAction,Fault} from '../hooks';
import type {Request} from '../api';

type Lifecycle={id:number;username:string;account_owner:string;account_purpose:string;enabled:boolean;account_expires_at:string|null;rotation_interval_days:number|null;credential_updated_at:string|null;rotation_due_at:string|null;lifecycle_status:string;rotation_status:string};
const statusLabels:Record<string,string>={active:'Активна',disabled:'Заблокирована',expiring:'Истекает',expired:'Просрочена',current:'Актуален',due_soon:'Скоро ротация',overdue:'Ротация просрочена',not_configured:'Не настроено',missing:'Нет реквизитов',unknown:'Неизвестно'};
const color=(s:string)=>['active','current'].includes(s)?'green':['expired','overdue','disabled','missing'].includes(s)?'red':['expiring','due_soon'].includes(s)?'orange':undefined;
const status=(s:string)=><Tag color={color(s)}>{statusLabels[s]??s}</Tag>;
const date=(s:string|null)=>s?new Date(s).toLocaleString():'—';
function LifecycleEditor({request,initial,refresh}:{request:Request;initial:Lifecycle;refresh:()=>void}){
 const [expires,setExpires]=useState(initial.account_expires_at?new Date(initial.account_expires_at).toISOString().slice(0,16):'');
 const [days,setDays]=useState(initial.rotation_interval_days===null?'':String(initial.rotation_interval_days));
 const a=useAction(refresh);
 const invalidDays=days!==''&&(!/^[0-9]+$/.test(days)||Number(days)<1||Number(days)>3650);
 const invalidDate=expires!==''&&!Number.isFinite(Date.parse(expires+'Z'));
 return <Space direction="vertical" className="full">
 <Alert type="info" message="Сроки являются диагностическими. Истечение срока пока не блокирует FreeRADIUS и не завершает активные сессии."/>
 <Space wrap>{status(initial.lifecycle_status)}{status(initial.rotation_status)}</Space>
 <span>Ответственный: {initial.account_owner||'—'}</span>
 <span>Назначение: {initial.account_purpose||'—'}</span>
 <label>Окончание действия (UTC, пусто — бессрочно)<input type="datetime-local" value={expires} onChange={e=>setExpires(e.target.value)} disabled={a.busy}/></label>
 <label>Интервал ротации (дни, пусто — не задан)<input type="number" min={1} max={3650} step={1} value={days} onChange={e=>setDays(e.target.value)} disabled={a.busy}/></label>
 <span>Последнее обновление реквизитов: {date(initial.credential_updated_at)}</span>
 <span>Следующая ротация: {date(initial.rotation_due_at)}</span>
 <Button type="primary" loading={a.busy} disabled={invalidDays||invalidDate||a.busy} onClick={()=>a.run(()=>request('identities/'+initial.id+'/lifecycle','PUT',{account_expires_at:expires?new Date(expires+'Z').toISOString():null,rotation_interval_days:days?Number(days):null}))}>Сохранить сроки</Button>
 </Space>
}
export function IdentityLifecycle({request,id,refresh}:{request:Request;id:number;refresh:()=>void}){
 const d=useData<Lifecycle>(request,'identities/'+id+'/lifecycle');
 return <Space direction="vertical" className="full"><Fault error={d.error}/>{d.data&&<LifecycleEditor key={id+'-'+d.data.account_expires_at+'-'+d.data.rotation_interval_days} request={request} initial={d.data} refresh={()=>{d.refresh();refresh()}}/>}</Space>
}
export default function ServiceAccountRegistry({request,refresh}:{request:Request;refresh:()=>void}){
 const [offset,setOffset]=useState(0);const [filter,setFilter]=useState('all');const [selected,setSelected]=useState<Lifecycle>();
 const d=useData<{items:Lifecycle[];more:boolean}>(request,'identities/service-registry?limit=100&offset='+offset);
 const rows=d.data?.items??[];
 return <Space direction="vertical" className="full">
 <Alert type="info" message="Реестр сроков действия и ротации. Фильтр применяется к текущей странице. Состояние Expired не означает отключение сетевого доступа."/>
 <Fault error={d.error}/>
 <Space wrap><Select value={filter} onChange={v=>setFilter(String(v))} options={[{value:'all',label:'Все на странице'},{value:'expired',label:'Просроченные УЗ'},{value:'expiring',label:'Истекают'},{value:'overdue',label:'Просрочена ротация'},{value:'due_soon',label:'Скоро ротация'}]}/><Button onClick={d.refresh}>Обновить</Button></Space>
 <Table<Lifecycle> rowKey="id" loading={d.loading} dataSource={rows.filter(r=>filter==='all'||r.lifecycle_status===filter||r.rotation_status===filter)} pagination={false} columns={[
 {title:'Логин',dataIndex:'username'},{title:'Ответственный',dataIndex:'account_owner'},{title:'Состояние УЗ',render:(_,r)=>status(r.lifecycle_status)},{title:'Доступ',render:(_,r)=><Tag color={r.enabled?'green':'red'}>{r.enabled?'Включён':'Отключён'}</Tag>},{title:'Истечение',render:(_,r)=>date(r.account_expires_at)},{title:'Ротация',render:(_,r)=>status(r.rotation_status)},{title:'Следующая ротация',render:(_,r)=>date(r.rotation_due_at)},{title:'Действия',render:(_,r)=><Button onClick={()=>setSelected(r)}>Настроить</Button>}
 ]}/>
 <Space wrap><Button disabled={!offset||d.loading} onClick={()=>setOffset(v=>Math.max(0,v-100))}>Назад</Button><span>Страница {offset/100+1}</span><Button disabled={!d.data?.more||d.loading} onClick={()=>setOffset(v=>v+100)}>Далее</Button></Space>
 <Modal title={selected?.username} open={!!selected} onCancel={()=>setSelected(undefined)} footer={null}>{selected&&<IdentityLifecycle key={selected.id} request={request} id={selected.id} refresh={()=>{d.refresh();refresh()}}/>}</Modal>
 </Space>
}
