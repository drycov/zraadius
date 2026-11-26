import {Alert,Button,Card,Form,Input,Select,Space,Table} from '../ui';
import {useAction,useData,Fault} from '../hooks';
import type {Request} from '../api';
export type ReplyProfile={id:number;name:string;description:string;role:string;filter_id:string|null};
type Role={name:string};
export function grantPayload(v:Record<string,unknown>){
 return v.profile_id?{profile_id:Number(v.profile_id)}:{role:v.role,filter_id:v.filter_id||null};
}
export function ProfileField({profiles}:{profiles:ReplyProfile[]}){
 return <Form.Item name="profile_id" label="Reply Profile"><Select options={[{value:0,label:'Вручную'},...profiles.map(p=>({value:p.id,label:p.name+' / '+p.role+(p.filter_id?' / '+p.filter_id:'')}))]}/></Form.Item>
}
export default function DeviceReplyProfiles({request,roles}:{request:Request;roles:Role[]}){
 const d=useData<ReplyProfile[]>(request,'device-aaa/reply-profiles');const a=useAction(d.refresh);const [form]=Form.useForm();
 return <Card title="Reply Attribute Profiles"><Space direction="vertical"><Fault error={d.error}/><Alert type="info" message="Шаблоны Mikrotik-Group и Filter-Id копируются в разрешение при назначении. Для изменения создайте новый профиль. Само создание профиля не предоставляет доступ."/>
 <Form form={form} layout="vertical" initialValues={{role:'read'}} onFinish={v=>a.run(()=>request('device-aaa/reply-profiles','POST',{...v,filter_id:v.filter_id||null}),()=>form.resetFields())}>
 <Form.Item name="name" label="Имя профиля" rules={[{required:true,max:64,pattern:/^[A-Za-z0-9_.-]+$/}]}><Input/></Form.Item>
 <Form.Item name="description" label="Описание"><Input maxLength={200}/></Form.Item>
 <Form.Item name="role" label="Mikrotik-Group" rules={[{required:true}]}><Select options={roles.map(r=>({value:r.name,label:r.name}))}/></Form.Item>
 <Form.Item name="filter_id" label="Filter-Id"><Input maxLength={64}/></Form.Item>
 <Button type="primary" htmlType="submit" loading={a.busy}>Создать профиль</Button></Form>
 <Table<ReplyProfile> rowKey="id" dataSource={d.data??[]} loading={d.loading} columns={[{title:'Профиль',dataIndex:'name'},{title:'Mikrotik-Group',dataIndex:'role'},{title:'Filter-Id',dataIndex:'filter_id'},{title:'Описание',dataIndex:'description'}]}/></Space></Card>
}
