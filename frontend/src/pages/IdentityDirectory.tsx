import {useState} from 'react';
import {Alert,Button,Checkbox,Form,Input,Space,Table,Tag,Popconfirm} from '../ui';
import {useAction,useData,Fault} from '../hooks';
import type {Request} from '../api';
type Entry={username:string;full_name:string;department:string;directory_enabled:boolean;compatible:boolean;local_exists:boolean};
type Result={items:Entry[];limited:boolean};
type Profile={id:number;name:string;host:string;base_dn:string;bind_dn:string;enabled:boolean};
export default function IdentityDirectory({request}:{request:Request}){
 const d=useData<Profile[]>(request,'identities/directory-profiles');
 const [result,setResult]=useState<Result>();const [editing,setEditing]=useState<Profile>();const [enabled,setEnabled]=useState(false);const [form]=Form.useForm();
 const [tested,setTested]=useState('');const a=useAction(d.refresh);
 const path='identities/directory-profiles';
 const reset=()=>{setEditing(undefined);setEnabled(false);form.resetFields()};
 return <Space direction="vertical" className="full">
 <Alert type="info" message="LDAPS TCP 636. Разрешённые хосты задаются администратором развёртывания. Пароль Bind не возвращается; при изменении профиля введите его заново. Только чтение каталога."/>
 <Fault error={d.error}/>
 <Table<Profile> rowKey="id" dataSource={d.data??[]} columns={[{title:'Имя',dataIndex:'name'},{title:'Хост',dataIndex:'host'},{title:'Статус',render:(_,r)=><Tag color={r.enabled?'green':'red'}>{r.enabled?'Включён':'Отключён'}</Tag>},{title:'Действия',render:(_,r)=><Space wrap><Button disabled={a.busy} onClick={()=>{setEditing(r);setEnabled(r.enabled);form.setFieldsValue({name:r.name,host:r.host,base_dn:r.base_dn,bind_dn:r.bind_dn,password:''})}}>Изменить</Button><Button disabled={a.busy} onClick={()=>a.run(async()=>{setTested('');await request(path+'/'+r.id+'/test','POST');setTested(r.name)})}>Проверить LDAPS</Button><Button disabled={a.busy||!r.enabled} onClick={()=>a.run(async()=>{setResult(undefined);setResult(await request<Result>('identities/directory-preview?profile_id='+r.id))})}>Каталог</Button><Popconfirm title="Удалить отключённый профиль?" onConfirm={()=>a.run(()=>request(path+'/'+r.id,'DELETE'))}><Button danger disabled={a.busy||r.enabled}>Удалить</Button></Popconfirm></Space>}]}/>
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
 <Table<Entry> rowKey="username" dataSource={result?.items??[]} columns={[{title:'Логин',dataIndex:'username'},{title:'ФИО',dataIndex:'full_name'},{title:'Подразделение',dataIndex:'department'},{title:'AD',render:(_,r)=><Tag color={r.directory_enabled?'green':'red'}>{r.directory_enabled?'Активен':'Отключён / неизвестно'}</Tag>},{title:'Unified Identity',render:(_,r)=>r.local_exists?'Существует':r.compatible?'Кандидат':'Несовместимый логин'}]}/>
 </Space>
}
