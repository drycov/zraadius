import {useState} from 'react';
import DirectoryGroups from './DirectoryGroups';
import {Alert,Button,Checkbox,Form,Input,Space,Table,Tag,Popconfirm} from '../ui';
import {useAction,useData,Fault} from '../hooks';
import type {Request} from '../api';
type Entry={object_guid:string|null;username:string;full_name:string;department:string;directory_enabled:boolean;compatible:boolean;local_exists:boolean};
type Result={items:Entry[];limited:boolean};
type Profile={id:number;name:string;host:string;base_dn:string;bind_dn:string;enabled:boolean};
type LinkedIdentity={object_guid:string;directory_username:string;directory_enabled:boolean;identity_id:number;username:string;enabled:boolean};
type IdentitySync={preview:boolean;status:string;identity_id:number;username:string;previous_directory_username?:string;directory_username?:string;previous_directory_enabled?:boolean;directory_enabled?:boolean;changed:boolean;authorization_applied:boolean};
type BulkSync={preview:boolean;linked:number;observed:number;changed:number;not_observed:number;incompatible:number;directory_disabled:number;directory_host?:string;failover_used:boolean};
type SyncHistory={action:string;subject:string;actor:string|null;created_at:string};
function DirectoryOperations({request,profileId}:{request:Request;profileId:number}){
 const path='identities/directory-profiles/'+profileId;
 const history=useData<SyncHistory[]>(request,path+'/sync-history');
 const a=useAction(history.refresh);
 const [result,setResult]=useState<BulkSync>();
 const [health,setHealth]=useState<{directory_host?:string;failover_used?:boolean}>();
 const run=(preview:boolean)=>a.run(async()=>{setResult(undefined);setResult(await request<BulkSync>(path+'/bulk-sync','POST',{preview}))});
 return <Space direction="vertical" className="full">
 <Alert type="info" message="Пакетная сверка AD: только метаданные связанных пользователей. Отсутствующие объекты не блокируются автоматически."/>
 <Space wrap><Button disabled={a.busy} onClick={()=>run(true)}>Предварительная сверка</Button>
 <Button disabled={a.busy} onClick={()=>a.run(async()=>{setHealth(undefined);setHealth(await request(path+'/test','POST'))})}>Проверить контроллер</Button>
 {result?.preview&&<Popconfirm title="Обновить метаданные всех связанных пользователей?" onConfirm={()=>run(false)}><Button type="primary" disabled={a.busy}>Применить сверку</Button></Popconfirm>}</Space>
 {health&&<Alert type="success" message={'LDAPS: '+(health.directory_host??'OK')+(health.failover_used?' (резервный DC)':'')}/>}
 {result&&<Alert type={result.not_observed?'warning':'info'} message={'Связано: '+result.linked+'; изменений: '+result.changed+'; отсутствует: '+result.not_observed+'; отключено в AD: '+result.directory_disabled+'; несовместимо: '+result.incompatible+'; DC: '+(result.directory_host??'—')}/>}
 <Fault error={history.error}/>
 <Table<SyncHistory> rowKey={r=>r.created_at+'-'+r.action+'-'+(r.actor??'')} dataSource={history.data??[]} columns={[{title:'История',dataIndex:'action'},{title:'Инициатор',dataIndex:'actor'},{title:'Время',dataIndex:'created_at'}]}/>
 </Space>
}
function LinkedIdentities({request,profileId}:{request:Request;profileId:number}){
 const path='identities/directory-profiles/'+profileId;
 const d=useData<LinkedIdentity[]>(request,path+'/linked-identities');
 const a=useAction(d.refresh);
 const [plan,setPlan]=useState<{guid:string;result:IdentitySync}>();
 return <Space direction="vertical" className="full">
 <Alert type="info" message="Связанные пользователи AD. Синхронизация обновляет только метаданные каталога, не локальный логин и не сетевой доступ. Список ограничен 1000 записями."/>
 <Fault error={d.error}/>
 <Table<LinkedIdentity> rowKey="identity_id" dataSource={d.data??[]} columns={[
 {title:'Локальный логин',dataIndex:'username'},
 {title:'Логин AD',dataIndex:'directory_username'},
 {title:'AD (сохранённое)',render:(_,r)=><Tag color={r.directory_enabled?'green':'red'}>{r.directory_enabled?'Активен':'Отключён / неизвестно'}</Tag>},
 {title:'Локальная запись',render:(_,r)=><Tag color={r.enabled?'green':'red'}>{r.enabled?'Активна':'Отключена'}</Tag>},
 {title:'Действия',render:(_,r)=><Button disabled={a.busy} onClick={()=>a.run(async()=>{setPlan(undefined);const result=await request<IdentitySync>(path+'/identity-sync','POST',{object_guid:r.object_guid,preview:true});setPlan({guid:r.object_guid,result})})}>Проверить состояние</Button>}
 ]}/>
 {plan&&<><Alert type={plan.result.status==='observed'?'info':'warning'} message={plan.result.status==='not_observed'?'Объект не найден в области поиска AD; это не подтверждение удаления.':plan.result.status==='incompatible_login'?'Несовместимый доменный логин; локальный логин не изменяется.':'Состояние AD: '+(plan.result.directory_enabled?'активен':'отключён / неизвестно')}/>
 {plan.result.directory_username!==undefined&&<span>Логин AD: {plan.result.previous_directory_username} → {plan.result.directory_username}</span>}
 <Space wrap>{plan.result.changed&&<Popconfirm title="Обновить только метаданные AD?" onConfirm={()=>a.run(async()=>{const result=await request<IdentitySync>(path+'/identity-sync','POST',{object_guid:plan.guid,preview:false});setPlan({guid:plan.guid,result})})}><Button type="primary" disabled={a.busy||!plan.result.preview}>Сохранить состояние</Button></Popconfirm>}<Button disabled={a.busy} onClick={()=>setPlan(undefined)}>Закрыть</Button></Space></>}
 </Space>
}
export default function IdentityDirectory({request}:{request:Request}){
 const d=useData<Profile[]>(request,'identities/directory-profiles');
 const [result,setResult]=useState<Result>();const [profileId,setProfileId]=useState<number>();const [plan,setPlan]=useState<Entry>();const [editing,setEditing]=useState<Profile>();const [enabled,setEnabled]=useState(false);const [form]=Form.useForm();
 const [tested,setTested]=useState('');const a=useAction(d.refresh);
 const path='identities/directory-profiles';
 const reset=()=>{setEditing(undefined);setEnabled(false);form.resetFields()};
 return <Space direction="vertical" className="full">
 <Alert type="info" message="LDAPS TCP 636. Разрешённые хосты задаются администратором развёртывания. Пароль Bind не возвращается; при изменении профиля введите его заново. Только чтение каталога."/>
 <Fault error={d.error}/>
 <Table<Profile> rowKey="id" dataSource={d.data??[]} columns={[{title:'Имя',dataIndex:'name'},{title:'Хост',dataIndex:'host'},{title:'Статус',render:(_,r)=><Tag color={r.enabled?'green':'red'}>{r.enabled?'Включён':'Отключён'}</Tag>},{title:'Действия',render:(_,r)=><Space wrap><Button disabled={a.busy} onClick={()=>{setEditing(r);setEnabled(r.enabled);form.setFieldsValue({name:r.name,host:r.host,base_dn:r.base_dn,bind_dn:r.bind_dn,password:''})}}>Изменить</Button><Button disabled={a.busy} onClick={()=>a.run(async()=>{setTested('');await request(path+'/'+r.id+'/test','POST');setTested(r.name)})}>Проверить LDAPS</Button><Button disabled={a.busy||!r.enabled} onClick={()=>a.run(async()=>{setResult(undefined);setPlan(undefined);setProfileId(r.id);setResult(await request<Result>('identities/directory-preview?profile_id='+r.id))})}>Каталог</Button><Popconfirm title="Удалить отключённый профиль?" onConfirm={()=>a.run(()=>request(path+'/'+r.id,'DELETE'))}><Button danger disabled={a.busy||r.enabled}>Удалить</Button></Popconfirm></Space>}]}/>
 {tested&&<Alert type="success" message={'LDAPS Bind и Base DN проверены: '+tested}/>}
 <Form form={form} layout="vertical" disabled={a.busy} onFinish={v=>a.run(()=>request(editing?path+'/'+editing.id:path,editing?'PUT':'POST',{...v,enabled}),reset)}>
 <Form.Item name="name" label="Имя профиля" rules={[{required:true,max:64}]}><Input/></Form.Item>
 <Form.Item name="host" label="DNS контроллера" rules={[{required:true,max:253}]}><Input placeholder="dc01.corp.local"/></Form.Item>
 <Form.Item name="base_dn" label="Base DN" rules={[{required:true,max:1024}]}><Input/></Form.Item>
 <Form.Item name="bind_dn" label="Bind DN" rules={[{required:true,max:1024}]}><Input/></Form.Item>
 <Form.Item name="password" label="Bind Password" rules={[{required:true,max:1024}]}><Input.Password autoComplete="new-password"/></Form.Item>
 <Checkbox checked={enabled} onChange={e=>setEnabled(e.target.checked)}>Включить профиль</Checkbox>
 <Space wrap><Button type="primary" htmlType="submit" loading={a.busy}>{editing?'Сохранить':'Создать профиль'}</Button><Button disabled={a.busy} onClick={reset}>Сбросить</Button></Space>
 </Form>
 {result?.limited&&<Alert type="warning" message="Выборка ограничена 200 записями."/>}
 <Table<Entry> rowKey="username" dataSource={result?.items??[]} columns={[{title:'Логин',dataIndex:'username'},{title:'ФИО',dataIndex:'full_name'},{title:'Подразделение',dataIndex:'department'},{title:'AD',render:(_,r)=><Tag color={r.directory_enabled?'green':'red'}>{r.directory_enabled?'Активен':'Отключён / неизвестно'}</Tag>},{title:'Unified Identity',render:(_,r)=>r.local_exists?'Существует':r.compatible?'Кандидат':'Несовместимый логин'},{title:'Импорт',render:(_,r)=><Button disabled={a.busy||!profileId||!r.object_guid||!r.compatible||!r.directory_enabled||r.local_exists} onClick={()=>a.run(async()=>{setPlan(undefined);await request(path+'/'+profileId+'/import','POST',{object_guid:r.object_guid,preview:true});setPlan(r)})}>Проверить</Button>}]}/>
 {plan&&profileId&&<><Alert type="warning" message={'Импорт '+plan.username+': запись будет заблокирована и не получит реквизиты или сервисы.'}/><Popconfirm title="Импортировать пользователя AD?" onConfirm={()=>a.run(async()=>{await request(path+'/'+profileId+'/import','POST',{object_guid:plan.object_guid,preview:false});setPlan(undefined);setResult(await request<Result>('identities/directory-preview?profile_id='+profileId))})}><Button type="primary" disabled={a.busy}>Импортировать</Button></Popconfirm></>}
 {profileId&&<><DirectoryOperations key={profileId} request={request} profileId={profileId}/><LinkedIdentities key={profileId} request={request} profileId={profileId}/><DirectoryGroups key={profileId} request={request} profileId={profileId}/></>}
 </Space>
}
