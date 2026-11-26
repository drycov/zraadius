import {useState} from 'react';
import {Alert,Button,Space,Table,Popconfirm,Checkbox} from '../ui';
import {useData,useAction,Fault} from '../hooks';
import type {Request} from '../api';
type Group={object_guid:string;name:string;distinguished_name:string};
type Inventory=Group&{id:number;observed_at:string;imported_members:number};
type Result={items:Group[];limited:boolean};
type LocalGroup={id:number;name:string};
type Mapping={groups:LocalGroup[];members:{id:number;username:string;enabled:boolean}[]};
type Sync={preview:boolean;name:string;observed_members:number;imported_members:number;added_count:number;removed_count:number;requires_removal_confirmation:boolean};
export default function DirectoryGroups({request,profileId}:{request:Request;profileId:number}){
 const path='identities/directory-profiles/'+profileId;
 const local=useData<LocalGroup[]>(request,'identities/groups');
 const [mapping,setMapping]=useState<Mapping>();const [mappingId,setMappingId]=useState<number>();const [targets,setTargets]=useState<number[]>([]);
 const d=useData<Inventory[]>(request,path+'/group-inventory');
 const [result,setResult]=useState<Result>();const [plan,setPlan]=useState<Group>();const [sync,setSync]=useState<Sync>();const a=useAction(d.refresh);
 const [confirmRemovals,setConfirmRemovals]=useState(false);
 return <Space direction="vertical" className="full">
 <Alert type="info" message="Группы безопасности AD: снимок прямого членства импортированных пользователей. Сетевые права не изменяются. Вложенные и primary groups не учитываются."/>
 <Fault error={d.error||local.error}/>
 <Button loading={a.busy} onClick={()=>a.run(async()=>{setConfirmRemovals(false);setPlan(undefined);setSync(undefined);setResult(undefined);setResult(await request<Result>(path+'/groups'))})}>Обнаружить группы AD</Button>
 {result?.limited&&<Alert type="warning" message="Выборка групп ограничена 200 записями."/>}
 <Table<Group> rowKey="object_guid" dataSource={result?.items??[]} columns={[{title:'Группа AD',dataIndex:'name'},{title:'DN',dataIndex:'distinguished_name'},{title:'Действие',render:(_,g)=><Button disabled={a.busy} onClick={()=>a.run(async()=>{setConfirmRemovals(false);setPlan(undefined);setSync(undefined);setSync(await request<Sync>(path+'/group-sync','POST',{object_guid:g.object_guid,preview:true}));setPlan(g)})}>Проверить членство</Button>}]}/>
 {plan&&sync?.preview&&<>
 <Alert type="info" message={sync.name+': найдено '+sync.observed_members+', импортировано '+sync.imported_members}/>
 <Table<{key:string;label:string;count:number}> rowKey="key" dataSource={[{key:'add',label:'Добавить',count:sync.added_count},{key:'remove',label:'Удалить',count:sync.removed_count},{key:'keep',label:'Без изменений',count:sync.imported_members-sync.added_count}]} columns={[{title:'Изменение',dataIndex:'label'},{title:'Количество',dataIndex:'count'}]}/>
 {sync.requires_removal_confirmation&&<>
 <Alert type="warning" message={'Из наблюдаемого состава будут удалены '+sync.removed_count+' участников. Сетевые права не изменяются.'}/>
 <Checkbox disabled={a.busy} checked={confirmRemovals} onChange={e=>setConfirmRemovals(e.target.checked)}>Подтверждаю удаление участников из снимка</Checkbox>
 </>}
 <Space wrap><Popconfirm title="Обновить наблюдаемый состав группы? Сервер повторно проверит каталог." onConfirm={()=>a.run(async()=>{if(sync.requires_removal_confirmation&&!confirmRemovals)return;setPlan(undefined);setSync(undefined);setConfirmRemovals(false);setSync(await request<Sync>(path+'/group-sync','POST',{object_guid:plan.object_guid,preview:false,confirm_removals:confirmRemovals}))})}><Button type="primary" disabled={a.busy||(sync.requires_removal_confirmation&&!confirmRemovals)}>Сохранить снимок</Button></Popconfirm><Button disabled={a.busy} onClick={()=>{setPlan(undefined);setSync(undefined);setConfirmRemovals(false)}}>Отменить</Button></Space>
 </>}
 {sync&&!sync.preview&&<Alert type="success" message={'Снимок сохранён: '+sync.imported_members+' локальных пользователей'}/>}
 <Table<Inventory> rowKey="id" dataSource={d.data??[]} columns={[{title:'Сохранённая группа',dataIndex:'name'},{title:'Участники',dataIndex:'imported_members'},{title:'Наблюдалась',dataIndex:'observed_at'},{title:'Политики',render:(_,g)=><Button disabled={a.busy} onClick={()=>a.run(async()=>{setMapping(undefined);setMappingId(undefined);const m=await request<Mapping>('identities/directory-groups/'+g.id+'/mapping');setMapping(m);setMappingId(g.id);setTargets(m.groups.map(x=>x.id))})}>Сопоставить</Button>}]}/>
 {mapping&&mappingId&&<><Alert type="warning" message="Сопоставление сохраняется как конфигурация. Сетевые права и ручные членства не меняются."/><span>Наблюдаемые пользователи: {mapping.members.map(x=>x.username).join(', ')||'—'}</span>{(local.data??[]).map(g=><Checkbox key={g.id} disabled={a.busy} checked={targets.includes(g.id)} onChange={e=>setTargets(old=>e.target.checked?[...old,g.id]:old.filter(x=>x!==g.id))}>{g.name}</Checkbox>)}<Popconfirm title="Сохранить сопоставление без изменения доступа?" onConfirm={()=>a.run(async()=>{await request('identities/directory-groups/'+mappingId+'/mapping','PUT',{group_ids:targets});setMapping(undefined);setMappingId(undefined)})}><Button type="primary" disabled={a.busy}>Сохранить сопоставление</Button></Popconfirm></>}
 </Space>
}
