import {useState} from 'react';
import {Alert,Button,Card,Form,Input,InputNumber,Modal,Popconfirm,Select,Space,Table,Tag,Typography} from '../ui';
import {useData,useAction,Fault} from '../hooks';
import type {Request} from '../api';
type Account={id:number;name:string;enabled:boolean};
type Token={id:string;label:string;scopes:string[];expires_at:string;revoked_at:string|null};
function Tokens({request,account}:{request:Request;account:Account}){
 const path='iam/service-accounts/'+account.id+'/tokens';
 const d=useData<Token[]>(request,path);const scopes=useData<string[]>(request,'iam/service-scopes');const a=useAction(d.refresh);
 const [form]=Form.useForm();const [issued,setIssued]=useState<string>();
 return <Card title={'Токены: '+account.name}><Space direction="vertical"><Fault error={d.error||scopes.error}/>
 {account.enabled&&<Form form={form} layout="vertical" initialValues={{lifetime_days:30,scopes:[]}} onFinish={v=>a.run(async()=>{const r=await request<{token:string}>(path,'POST',v);setIssued(r.token)},()=>form.resetFields())}>
 <Form.Item name="label" label="Название токена" rules={[{required:true,max:64}]}><Input maxLength={64}/></Form.Item>
 <Form.Item name="scopes" label="Разрешения" rules={[{required:true}]}><Select mode="multiple" options={(scopes.data??[]).map(x=>({value:x,label:x}))}/></Form.Item>
 <Form.Item name="lifetime_days" label="Срок действия, дней" rules={[{required:true}]}><InputNumber min={1} max={365}/></Form.Item>
 <Button type="primary" htmlType="submit" loading={a.busy}>Выпустить токен</Button></Form>}
 <Modal open={!!issued} title="Сохраните токен — повторно не отображается" onCancel={()=>setIssued(undefined)} onOk={()=>setIssued(undefined)}><Alert type="warning" message="Храните токен в защищённом хранилище."/><Typography.Text copyable>{issued}</Typography.Text></Modal>
 <Table<Token> rowKey="id" dataSource={d.data??[]} loading={d.loading} columns={[{title:'Название',dataIndex:'label'},{title:'Разрешения',render:(_,x)=>x.scopes.join(', ')},{title:'Истекает',dataIndex:'expires_at'},{title:'Статус',render:(_,x)=><Tag color={x.revoked_at?'red':new Date(x.expires_at).getTime()<=Date.now()?'orange':'green'}>{x.revoked_at?'Отозван':new Date(x.expires_at).getTime()<=Date.now()?'Истёк':'Активен'}</Tag>},{title:'',render:(_,x)=><Popconfirm title="Отозвать токен?" onConfirm={()=>a.run(()=>request(path+'/'+x.id,'DELETE'))}><Button danger disabled={!!x.revoked_at||a.busy}>Отозвать</Button></Popconfirm>}]}/></Space></Card>
}
export default function ServiceAccounts({request}:{request:Request}){
 const d=useData<Account[]>(request,'iam/service-accounts');const a=useAction(d.refresh);const [form]=Form.useForm();const [selected,setSelected]=useState<number>();const account=d.data?.find(x=>x.id===selected);
 return <Space direction="vertical"><Fault error={d.error}/><Card title="Сервисные учётные записи"><Form form={form} layout="inline" onFinish={v=>a.run(()=>request('iam/service-accounts','POST',v),()=>form.resetFields())}><Form.Item name="name" label="Имя интеграции" rules={[{required:true,max:64}]}><Input placeholder="zbss-sync" maxLength={64}/></Form.Item><Button type="primary" htmlType="submit" loading={a.busy}>Создать</Button></Form>
 <Table<Account> rowKey="id" loading={d.loading} dataSource={d.data??[]} columns={[{title:'Имя',dataIndex:'name'},{title:'Статус',render:(_,x)=><Tag color={x.enabled?'green':'red'}>{x.enabled?'Активна':'Отключена'}</Tag>},{title:'',render:(_,x)=><Space wrap><Button onClick={()=>setSelected(x.id)}>Токены</Button><Popconfirm title="Отключить аккаунт и отозвать все токены без возможности восстановления?" onConfirm={()=>a.run(()=>request('iam/service-accounts/'+x.id+'/disable','PUT'))}><Button danger disabled={!x.enabled||a.busy}>Отключить</Button></Popconfirm></Space>}]}/></Card>{account&&<Tokens key={account.id} account={account} request={request}/>}</Space>
}
