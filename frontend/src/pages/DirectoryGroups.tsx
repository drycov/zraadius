import {useState} from 'react';
import {Alert,Button,Space,Table,Popconfirm,Checkbox} from '../ui';
import {useData,useAction,Fault} from '../hooks';
import type {Request} from '../api';
type Group={object_guid:string;name:string;distinguished_name:string};
type Inventory=Group&{id:number;observed_at:string;imported_members:number};
type Result={items:Group[];limited:boolean};
type LocalGroup={id:number;name:string};
type Mapping={groups:LocalGroup[];members:{id:number;username:string;enabled:boolean}[]};
type Sync={preview:boolean;name:string;observed_members:number;imported_members:number};
export default function DirectoryGroups({request,profileId}:{request:Request;profileId:number}){
 const path='identities/directory-profiles/'+profileId;
 const local=useData<LocalGroup[]>(request,'identities/groups');
 const [mapping,setMapping]=useState<Mapping>();const [mappingId,setMappingId]=useState<number>();const [targets,setTargets]=useState<number[]>([]);
 const d=useData<Inventory[]>(request,path+'/group-inventory');
 const [result,setResult]=useState<Result>();const [plan,setPlan]=useState<Group>();const [sync,setSync]=useState<Sync>();const a=useAction(d.refresh);
 return <Space direction="vertical" className="full">
 <Alert type="info" message="Группы безопасности AD: снимок прямого членства импортированных пользователей. Сетевые права не изменяются. Вложенные и primary groups не учитываются."/>
 <Fault error={d.error||local.error}/>
 <Button loading={a.busy} onClick={()=>a.run(async()=>{setPlan(undefined);setSync(undefined);setResult(undefined);setResult(await request<Result>(path+'/groups'))})}>Обнаружить группы AD</Button>
 {result?.limited&&<Alert type="warning" message="Выборка групп ограничена 200 записями."/>}
 <Table<Group> rowKey="object_guid" dataSource={result?.items??[]} columns={[{title:'Группа AD',dataIndex:'name'},{title:'DN',dataIndex:'distinguished_name'},{title:'Действие',render:(_,g)=><Button disabled={a.busy} onClick={()=>a.run(async()=>{setPlan(undefined);setSync(undefined);setSync(await request<Sync>(path+'/group-sync','POST',{object_guid:g.object_guid,preview:true}));setPlan(g)})}>Проверить членство</Button>}]}/>
 {plan&&sync?.preview&&<><Alert type="info" message={sync.name+': найдено '+sync.observed_members+', импортировано '+sync.imported_members}/><Popconfirm title="Обновить наблюдаемый состав группы? Права доступа не изменятся." onConfirm={()=>a.run(async()=>{setSync(await request<Sync>(path+'/group-sync','POST',{object_guid:plan.object_guid,preview:false}));setPlan(undefined)})}><Button type="primary" disabled={a.busy}>Сохранить снимок</Button></Popconfirm></>}
 {sync&&!sync.preview&&<Alert type="success" message={'Снимок сохранён: '+sync.imported_members+' локальных пользователей'}/>}
 <Table<Inventory> rowKey="id" dataSource={d.data??[]} columns={[{title:'Сохранённая группа',dataIndex:'name'},{title:'Участники',dataIndex:'imported_members'},{title:'Наблюдалась',dataIndex:'observed_at'},{title:'Политики',render:(_,g)=><Button disabled={a.busy} onClick={()=>a.run(async()=>{setMapping(undefined);setMappingId(undefined);const m=await request<Mapping>('identities/directory-groups/'+g.id+'/mapping');setMapping(m);setMappingId(g.id);setTargets(m.groups.map(x=>x.id))})}>Сопоставить</Button>}]}/>
 {mapping&&mappingId&&<><Alert type="warning" message="Сопоставление сохраняется как конфигурация. Сетевые права и ручные членства не меняются."/><span>Наблюдаемые пользователи: {mapping.members.map(x=>x.username).join(', ')||'—'}</span>{(local.data??[]).map(g=><Checkbox key={g.id} disabled={a.busy} checked={targets.includes(g.id)} onChange={e=>setTargets(old=>e.target.checked?[...old,g.id]:old.filter(x=>x!==g.id))}>{g.name}</Checkbox>)}<Popconfirm title="Сохранить сопоставление без изменения доступа?" onConfirm={()=>a.run(async()=>{await request('identities/directory-groups/'+mappingId+'/mapping','PUT',{group_ids:targets});setMapping(undefined);setMappingId(undefined)})}><Button type="primary" disabled={a.busy}>Сохранить сопоставление</Button></Popconfirm></>}
 </Space>
}
