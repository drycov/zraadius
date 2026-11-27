import {useState} from 'react';
import {Alert,Button,Input,Select,Space,Table,Tag} from '../ui';
import {useData,Fault} from '../hooks';
import type {Request} from '../api';
import IdentityReconciliation from './IdentityReconciliation';
type Item={id:number;username:string;account_type:'person'|'service';enabled:boolean;expired:boolean;source:string;template_id:number|null;template_name:string|null;status:'in_sync'|'review_required'|'protected'|'blocked';score:number|null;drift_services:string[];protected_services:string[];protected_drift_count:number;missing_services:string[];extra_services:string[];parameter_drift_count:number};
type GlobalSummary={scope:string;total_accounts:number;complete:boolean;reason?:string;summary:Record<string,number>|null;mean_account_score:number|null;measured_accounts?:number};
type Page={items:Item[];page_summary:Record<string,number>;next_after_id:number|null};
const statuses:Record<Item['status'],string>={in_sync:'Соответствует',review_required:'Требуется проверка',protected:'Защищённые расхождения',blocked:'Профиль не определён'};
const sources:Record<string,string>={direct:'Прямой',group:'Групповой',none:'Без профиля',conflict:'Конфликт',invalid_direct:'Недоступный прямой',invalid_group:'Недоступный групповой'};
export default function PolicyCompliance({request}:{request:Request}){
 const [query,setQuery]=useState('');
 const [search,setSearch]=useState('');
 const [kind,setKind]=useState('all');
 const [group,setGroup]=useState('all');
 const [status,setStatus]=useState('all');
 const [cursors,setCursors]=useState<number[]>([0]);
 const [selected,setSelected]=useState<Item>();
 const groups=useData<{id:number;name:string}[]>(request,'identities/groups');
 const cursor=cursors[cursors.length-1];
 const filters='q='+encodeURIComponent(search)+(kind==='all'?'':'&account_type='+kind)+(group==='all'?'':'&group_id='+group);
 const d=useData<Page>(request,'identities/policy-compliance?limit=50&after_id='+cursor+'&'+filters);
 const global=useData<GlobalSummary>(request,'identities/policy-compliance-summary?'+filters);
 const reset=()=>{setCursors([0]);setSelected(undefined)};
 const summary=d.data?.page_summary;
 const rows=(d.data?.items??[]).filter(r=>status==='all'||r.status===status);
 return <Space direction="vertical" className="full">
 <Alert type="info" message="Глобальная сводка учитывает поиск, тип УЗ и группу. Фильтр состояния применяется только к таблице текущей страницы. Score оценивает прямые назначения и заданные параметры, а не фактическую RADIUS-авторизацию."/>
 <Fault error={d.error||groups.error}/>
 <Space wrap><Input value={query} maxLength={200} placeholder="Поиск по логину" onChange={e=>setQuery(e.target.value)}/><Button onClick={()=>{reset();setSearch(query.trim())}}>Найти</Button>
 <Select value={kind} onChange={v=>{reset();setKind(String(v))}} options={[{value:'all',label:'Все типы'},{value:'person',label:'Персональные'},{value:'service',label:'Сервисные'}]}/>
 <Select value={group} onChange={v=>{reset();setGroup(String(v))}} options={[{value:'all',label:'Все группы'},...(groups.data??[]).map(g=>({value:String(g.id),label:g.name}))]}/>
 <Select value={status} onChange={v=>{setSelected(undefined);setStatus(String(v))}} options={[{value:'all',label:'Все состояния страницы'},...Object.entries(statuses).map(([value,label])=>({value,label}))]}/>
 <Button disabled={d.loading} onClick={()=>{setSelected(undefined);d.refresh();groups.refresh();global.refresh()}}>Обновить</Button></Space>
 <strong>Сводка по отфильтрованному каталогу</strong>
 <Fault error={global.error}/>
 {global.loading&&<span>Расчёт глобальных показателей…</span>}
 {global.data&&<><Space wrap><Tag>Всего УЗ: {global.data.total_accounts}</Tag>{global.data.complete&&<><Tag>Измерено: {global.data.measured_accounts??0}</Tag><Tag>Средний Score: {global.data.mean_account_score===null?'N/A':global.data.mean_account_score+'%'}</Tag></>}</Space>
 {!global.data.complete&&<Alert type="warning" message="Полный расчёт недоступен: превышен интерактивный лимит 500 УЗ. Уточните фильтры."/>}
 {global.data.complete&&global.data.summary&&<Space wrap>{[['in_sync','Соответствуют'],['review_required','Требуют проверки'],['protected','Защищённые'],['blocked','Не определены'],['conflicts','Конфликты'],['unassigned','Без профиля'],['expired','Просрочены'],['disabled','Заблокированы'],['with_overrides','С исключениями']].map(([key,label])=><Tag key={key}>{label}: {global.data?.summary?.[key]??0}</Tag>)}</Space>}</>}
 <strong>Текущая страница (до фильтра состояния)</strong>
 {summary&&<Space wrap>{[['accounts','УЗ на странице'],['in_sync','Соответствуют'],['review_required','Требуют проверки'],['protected','Защищённые'],['blocked','Без разрешённого профиля'],['conflicts','Конфликты'],['unassigned','Без профиля'],['expired','Просрочены'],['disabled','Заблокированы'],['with_overrides','С исключениями']].map(([key,label])=><Tag key={key}>{label}: {summary[key]??0}</Tag>)}</Space>}
 <Table<Item> rowKey="id" pagination={false} loading={d.loading} dataSource={rows} columns={[
 {title:'Логин',dataIndex:'username'},{title:'Тип',render:(_,r)=>r.account_type==='person'?'Пользователь':'Сервисная УЗ'},
 {title:'Профиль',render:(_,r)=><Space direction="vertical"><span>{r.template_name??'—'}</span><span>{sources[r.source]??r.source}</span></Space>},
 {title:'Соответствие',render:(_,r)=><Tag color={r.status==='in_sync'?'green':r.status==='blocked'?'red':'orange'}>{r.score===null?'N/A':r.score+'%'} · {statuses[r.status]}</Tag>},
 {title:'Расхождения',render:(_,r)=><Space direction="vertical"><span>{r.drift_services.join(', ')||'—'}</span><span>Параметры: {r.parameter_drift_count}</span></Space>},
 {title:'Защита',render:(_,r)=>r.protected_services.join(', ')||'—'},
 {title:'УЗ',render:(_,r)=><Tag color={!r.enabled||r.expired?'red':'green'}>{!r.enabled?'Заблокирована':r.expired?'Просрочена':'Активна'}</Tag>},
 {title:'Действия',render:(_,r)=><Button onClick={()=>setSelected(r)}>Согласование</Button>}
 ]}/>
 <Space wrap><Button disabled={d.loading||cursors.length<=1} onClick={()=>{setSelected(undefined);setCursors(old=>old.slice(0,-1))}}>Назад</Button><span>Страница {cursors.length}</span><Button disabled={d.loading||d.data?.next_after_id==null} onClick={()=>{const next=d.data?.next_after_id;if(next!=null){setSelected(undefined);setCursors(old=>[...old,next])}}}>Далее</Button></Space>
 {selected&&<Space direction="vertical" className="full"><Space wrap><strong>Согласование: {selected.username}</strong><Button onClick={()=>{setSelected(undefined);d.refresh();global.refresh()}}>Закрыть и обновить</Button></Space><IdentityReconciliation key={selected.id} request={request} id={selected.id}/></Space>}
 </Space>
}
