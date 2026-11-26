import {useState} from 'react';
import {Alert,Button,Card,Form,Input,Popconfirm,Select,Space,Table,Tag} from '../ui';
import {useAction,useData,Fault} from '../hooks';
import type {Request,Nas} from '../api';
type User={id:number;username:string;enabled:boolean};
type Role={name:string;description:string};
type Group={id:number;name:string;description:string};
type Grant={nas_id:number;shortname:string;role:string;filter_id:string|null};
function GroupDetails({request,group,users,nas,roles}:{request:Request;group:Group;users:User[];nas:Nas[];roles:Role[]}){
 const path='device-aaa/groups/'+group.id;const m=useData<User[]>(request,path+'/members');const g=useData<Grant[]>(request,path+'/grants');const a=useAction(()=>{m.refresh();g.refresh()});
 const [member]=Form.useForm();const [grant]=Form.useForm();const eligible=nas.filter(x=>x.type==='mikrotik'&&x.services?.includes('device-aaa'));
 return <Card title={'Группа: '+group.name}><Space direction="vertical"><Fault error={m.error||g.error}/>
 <Form form={member} layout="inline" onFinish={v=>a.run(()=>request(path+'/members/'+v.user_id,'PUT'),()=>member.resetFields())}><Form.Item name="user_id" label="Пользователь" rules={[{required:true}]}><Select options={users.filter(x=>!(m.data??[]).some(y=>y.id===x.id)).map(x=>({value:x.id,label:x.username}))}/></Form.Item><Button type="primary" htmlType="submit" loading={a.busy}>Добавить участника</Button></Form>
 <Table<User> rowKey="id" dataSource={m.data??[]} loading={m.loading} columns={[{title:'Участник',dataIndex:'username'},{title:'Статус',render:(_,x)=><Tag>{x.enabled?'Активен':'Отключён'}</Tag>},{title:'',render:(_,x)=><Popconfirm title="Удалить участника из группы?" onConfirm={()=>a.run(()=>request(path+'/members/'+x.id,'DELETE'))}><Button danger disabled={a.busy}>Удалить</Button></Popconfirm>}]}/>
 <Alert type="warning" message="Назначение применяется ко всем участникам. Различающиеся групповые разрешения без индивидуального назначения приводят к отказу."/>
 <Form form={grant} layout="inline" initialValues={{role:'read'}} disabled={!eligible.length||a.busy} onFinish={v=>a.run(()=>request(path+'/grants/'+v.nas_id,'PUT',{role:v.role,filter_id:v.filter_id||null}),()=>grant.resetFields())}><Form.Item name="nas_id" label="NAS" rules={[{required:true}]}><Select options={eligible.map(x=>({value:x.id,label:x.shortname}))}/></Form.Item><Form.Item name="role" label="RouterOS Group" rules={[{required:true}]}><Select options={roles.map(x=>({value:x.name,label:x.name}))}/></Form.Item><Form.Item name="filter_id" label="Filter-Id"><Input maxLength={64}/></Form.Item><Popconfirm title="Назначить доступ всем участникам группы?" onConfirm={()=>grant.submit()}><Button type="primary" disabled={!eligible.length||a.busy}>Назначить</Button></Popconfirm></Form>
 <Table<Grant> rowKey="nas_id" dataSource={g.data??[]} loading={g.loading} columns={[{title:'NAS',dataIndex:'shortname'},{title:'Роль',dataIndex:'role'},{title:'Filter-Id',dataIndex:'filter_id'},{title:'',render:(_,x)=><Popconfirm title="Отозвать групповое разрешение?" onConfirm={()=>a.run(()=>request(path+'/grants/'+x.nas_id,'DELETE'))}><Button danger disabled={a.busy}>Отозвать</Button></Popconfirm>}]}/></Space></Card>
}
export default function DeviceGroups({request,users,nas,roles}:{request:Request;users:User[];nas:Nas[];roles:Role[]}){
 const d=useData<Group[]>(request,'device-aaa/groups');const a=useAction(d.refresh);const [form]=Form.useForm();const [selected,setSelected]=useState<number>();const group=d.data?.find(x=>x.id===selected);
 return <Space direction="vertical" className="full"><Card title="Группы пользователей Device AAA"><Fault error={d.error}/><Form form={form} layout="inline" onFinish={v=>a.run(()=>request('device-aaa/groups','POST',v),()=>form.resetFields())}><Form.Item name="name" label="Имя группы" rules={[{required:true,max:64,pattern:/^[A-Za-z0-9_.-]+$/}]}><Input placeholder="NOC"/></Form.Item><Form.Item name="description" label="Описание"><Input maxLength={200}/></Form.Item><Button type="primary" htmlType="submit" loading={a.busy}>Создать</Button></Form><Table<Group> rowKey="id" dataSource={d.data??[]} loading={d.loading} columns={[{title:'Группа',dataIndex:'name'},{title:'Описание',dataIndex:'description'},{title:'',render:(_,x)=><Button onClick={()=>setSelected(x.id)}>Участники и доступ</Button>}]}/></Card>{group&&<GroupDetails key={group.id} request={request} group={group} users={users} nas={nas} roles={roles}/>}</Space>
}
export function EffectiveGrants({request,userId}:{request:Request;userId:number}){
 const d=useData<(Grant&{source:string})[]>(request,'device-aaa/users/'+userId+'/effective-grants');
 return <Card title="Действующие разрешения" extra={<Button onClick={d.refresh}>Обновить</Button>}><Fault error={d.error}/><Table<Grant&{source:string}> rowKey="nas_id" dataSource={d.data??[]} loading={d.loading} columns={[{title:'NAS',dataIndex:'shortname'},{title:'Роль',dataIndex:'role'},{title:'Filter-Id',dataIndex:'filter_id'},{title:'Источник',dataIndex:'source'}]}/></Card>
}
