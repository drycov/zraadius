import {useState} from 'react';
import {Alert,Button,Select,Space,Table} from '../ui';
import {useData,Fault} from '../hooks';
import type {Request} from '../api';
type Event={source:string;id:string;event_at:string;event:string;actor:string|null;nas:string|null};
type Result={items:Event[];more:boolean};
function csvCell(value:unknown){
 const raw=String(value??'');
 const safe=/^[\s]*[=+\-@]|^[\t\r\n]/.test(raw)?"'"+raw:raw;
 return '"'+safe.replace(/"/g,'""')+'"';
}
export default function IdentityAudit({request,id}:{request:Request;id:number}){
 const [source,setSource]=useState('all');const [offset,setOffset]=useState(0);
 const d=useData<Result>(request,'identities/'+id+'/audit?source='+source+'&limit=100&offset='+offset);
 const exportPage=()=>{
 const rows=d.data?.items??[];
 const csv=[['time','source','event','actor','nas'].map(csvCell).join(','),...rows.map(r=>[r.event_at,r.source,r.event,r.actor,r.nas].map(csvCell).join(','))].join('\r\n');
 const url=URL.createObjectURL(new Blob(['\uFEFF',csv],{type:'text/csv;charset=utf-8'}));
 const a=document.createElement('a');a.href=url;a.download='identity-'+id+'-audit-page-'+(offset/100+1)+'.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)
 };
 return <Space direction="vertical" className="full">
 <Alert type="info" message="События после создания единой записи. RADIUS и Device AAA сопоставляются по логину; это наблюдения, а не подтверждение личности или конкретной политики. Доступ только персональному администратору."/>
 <Fault error={d.error}/>
 <Space wrap><Select value={source} options={[{value:'all',label:'Все события'},{value:'management',label:'Управление'},{value:'radius',label:'RADIUS'},{value:'device',label:'Device AAA'}]} onChange={v=>{setSource(String(v));setOffset(0)}}/><Button onClick={d.refresh} loading={d.loading}>Обновить</Button><Button disabled={d.loading||!d.data?.items.length} onClick={exportPage}>CSV текущей страницы</Button></Space>
 <Table<Event> rowKey={r=>r.source+':'+r.id} loading={d.loading} dataSource={d.data?.items??[]} pagination={false} columns={[{title:'Время',dataIndex:'event_at'},{title:'Источник',dataIndex:'source'},{title:'Событие',dataIndex:'event'},{title:'Инициатор',dataIndex:'actor'},{title:'NAS',dataIndex:'nas'}]}/>
 <Space wrap><Button disabled={!offset||d.loading} onClick={()=>setOffset(x=>Math.max(0,x-100))}>Назад</Button><span>Страница {offset/100+1}</span><Button disabled={d.loading||!d.data?.more||offset>=100000} onClick={()=>setOffset(x=>x+100)}>Далее</Button></Space>
 </Space>
}
