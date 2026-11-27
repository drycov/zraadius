import {useState} from 'react';
import {Alert,Button,Checkbox,Input,Select,Space,Table,Tag} from '../ui';
import {useData,useAction,Fault} from '../hooks';
import type {Request} from '../api';
import type {AccessTemplate} from './AccessTemplates';
type Identity={id:number;username:string;account_type:'person'|'service';access_template_id:number|null};
type Result={selected:number;changed:number;items:{identity_id:number;username:string;previous_template_id:number|null;missing_services:string[];extra_services:string[];parameter_drift_count:number}[]};
export default function BulkAccessProfiles({request,refresh}:{request:Request;refresh:()=>void}){
 const [kind,setKind]=useState('person');const [query,setQuery]=useState('');const [search,setSearch]=useState('');const [offset,setOffset]=useState(0);
 const [ids,setIds]=useState<number[]>([]);const [target,setTarget]=useState('none');const [preview,setPreview]=useState<Result>();const [previewBusy,setPreviewBusy]=useState(false);const [error,setError]=useState('');
 const d=useData<Identity[]>(request,'identities?limit=101&offset='+offset+'&account_type='+kind+'&q='+encodeURIComponent(search));
 const t=useData<AccessTemplate[]>(request,'identities/access-templates');
 const a=useAction(()=>{setPreview(undefined);setIds([]);d.refresh();refresh()});
 const busy=a.busy||previewBusy;
 const rows=(d.data??[]).slice(0,100);
 const valid=target==='none'||!!t.data?.some(x=>String(x.id)===target&&x.enabled&&x.account_type===kind);
 const payload={identity_ids:ids,template_id:target==='none'?null:Number(target)};
 const changeIds=(next:number[])=>{setIds(next.slice(0,100));setPreview(undefined);setError('')};
 const toggle=(id:number,checked:boolean)=>changeIds(checked?[...new Set([...ids,id])]:ids.filter(x=>x!==id));
 return <Space direction="vertical" className="full">
 <Alert type="info" message="Массовая привязка до 100 учётных записей. Сетевые права не изменяются. Выбор сохраняется при переходе между страницами."/>
 <Fault error={d.error||t.error||error}/>
 <Space wrap><Select disabled={busy} value={kind} options={[{value:'person',label:'Пользователи'},{value:'service',label:'Сервисные УЗ'}]} onChange={v=>{setKind(String(v));setTarget('none');setOffset(0);changeIds([])}}/><Input value={query} disabled={busy} placeholder="Поиск пользователей" onChange={e=>setQuery(e.target.value)}/><Button disabled={busy} onClick={()=>{setSearch(query.trim());setOffset(0)}}>Найти</Button></Space>
 <Select value={target} disabled={busy||t.loading} options={[{value:'none',label:'Отвязать профиль'},...(t.data??[]).filter(x=>x.enabled&&x.account_type===kind).map(x=>({value:String(x.id),label:x.name}))]} onChange={v=>{setTarget(String(v));setPreview(undefined)}}/>
 <Space wrap><Tag>Выбрано: {ids.length}/100</Tag><Button disabled={busy||!rows.length} onClick={()=>changeIds([...new Set([...ids,...rows.map(r=>r.id)])])}>Выбрать страницу (до лимита)</Button><Button disabled={busy||!ids.length} onClick={()=>changeIds([])}>Очистить выбор</Button></Space>
 <Table<Identity> rowKey="id" pagination={false} loading={d.loading} dataSource={rows} columns={[{title:'Выбор',render:(_,r)=><Checkbox checked={ids.includes(r.id)} disabled={busy||(!ids.includes(r.id)&&ids.length>=100)} onChange={e=>toggle(r.id,e.target.checked)}/>},{title:'Логин',dataIndex:'username'},{title:'Профиль',render:(_,r)=>r.access_template_id===null?'—':t.data?.find(x=>x.id===r.access_template_id)?.name??'#'+r.access_template_id}]}/>
 <Space wrap><Button disabled={busy||!offset||d.loading} onClick={()=>setOffset(v=>Math.max(0,v-100))}>Назад</Button><span>Страница {offset/100+1}</span><Button disabled={busy||d.loading||(d.data?.length??0)<=100} onClick={()=>setOffset(v=>v+100)}>Далее</Button></Space>
 <Button disabled={busy||!ids.length||!valid} loading={previewBusy} onClick={async()=>{setPreviewBusy(true);setPreview(undefined);setError('');try{setPreview(await request<Result>('identities/bulk-access-profile','PUT',{...payload,preview:true}))}catch(e){setError(e instanceof Error?e.message:'Ошибка предпросмотра')}finally{setPreviewBusy(false)}}}>Предпросмотр</Button>
 {preview&&<><Tag>Изменяемых привязок: {preview.changed}/{preview.selected}</Tag><Table<Result['items'][number]> rowKey="identity_id" pagination={false} dataSource={preview.items} columns={[{title:'Логин',dataIndex:'username'},{title:'Отсутствующие',render:(_,r)=>r.missing_services.join(', ')||'—'},{title:'Дополнительные',render:(_,r)=>r.extra_services.join(', ')||'—'},{title:'Расхождения параметров',dataIndex:'parameter_drift_count'}]}/><Alert type="warning" message="Подтверждение сохранит только привязки. Сервер повторно проверит совместимость."/><Button type="primary" disabled={busy||!valid||!preview.changed} loading={a.busy} onClick={()=>a.run(()=>request('identities/bulk-access-profile','PUT',{...payload,preview:false}))}>Подтвердить массовое назначение</Button></>}
 </Space>
}
