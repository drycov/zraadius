import {useState} from 'react';
import {Alert,Button,Card,Form,Input,InputNumber,Modal,Popconfirm,Select,Space,Table,Tag} from '../ui';
import Disclosure from '../ui/Disclosure';
import {useData,useAction,Fault} from '../hooks';
import type {Request,Nas} from '../api';
type Profile={id:number;name:string;pool:string|null;interim_seconds:number;description:string};
type User={id:number;username:string;enabled:boolean;nas:string;profile:string;static_ip:string|null;pool:string|null;description:string};
export default function PppPage({request}:{request:Request}){
 const p=useData<Profile[]>(request,'ppp/profiles');const n=useData<Nas[]>(request,'nas');const [offset,setOffset]=useState(0);const u=useData<User[]>(request,'ppp/l2tp/users?limit=100&offset='+offset);
 const a=useAction(()=>{p.refresh();u.refresh()});const [pf]=Form.useForm();const [uf]=Form.useForm();const [passwordForm]=Form.useForm();const [target,setTarget]=useState<User>();
 const eligible=(n.data??[]).filter(x=>x.type==='mikrotik'&&x.services?.includes('l2tp'));
 return <Space direction="vertical" className="full"><Alert type="warning" message="L2TP: отдельная база пользователей. PPP-профили и пулы должны существовать на RouterOS. Не переключайте действующий NAS до тестирования."/><Fault error={p.error||n.error||u.error}/>
 <Disclosure title="PPP Profiles" meta={String(p.data?.length??0)} defaultOpen>
 <Form form={pf} layout="inline" initialValues={{interim_seconds:300}} onFinish={v=>a.run(()=>request('ppp/profiles','POST',{...v,pool:v.pool||null}),()=>pf.resetFields())}><Form.Item name="name" label="Имя PPP Profile" rules={[{required:true,max:64}]}><Input placeholder="vpn_ovn-lu-p"/></Form.Item><Form.Item name="pool" label="Remote Pool"><Input placeholder="Satory_VPN_2"/></Form.Item><Form.Item name="interim_seconds" label="Interim (сек)" rules={[{required:true}]}><InputNumber min={60} max={86400}/></Form.Item><Form.Item name="description" label="Описание"><Input maxLength={200}/></Form.Item><Button type="primary" htmlType="submit" loading={a.busy}>Создать профиль</Button></Form>
 <Table<Profile> rowKey="id" loading={p.loading} dataSource={p.data??[]} columns={[{title:'PPP Profile',dataIndex:'name'},{title:'Pool',dataIndex:'pool'},{title:'Interim',dataIndex:'interim_seconds'},{title:'Описание',dataIndex:'description'}]}/></Disclosure>
 <Disclosure title="L2TP Users" defaultOpen>
 {!eligible.length&&<Alert type="warning" message="Назначьте сервис l2tp зарегистрированному MikroTik NAS."/>}
 <Form form={uf} layout="vertical" disabled={!eligible.length||!p.data?.length||a.busy} onFinish={v=>a.run(()=>request('ppp/l2tp/users','POST',{...v,static_ip:v.static_ip||null}),()=>uf.resetFields())}>
 <Form.Item name="username" label="Username" rules={[{required:true,max:64}]}><Input/></Form.Item>
 <Form.Item name="password" label="Пароль PPP" rules={[{required:true,min:16,max:128}]}><Input.Password autoComplete="new-password"/></Form.Item>
 <Form.Item name="nas_id" label="NAS" rules={[{required:true}]}><Select options={eligible.map(x=>({value:x.id,label:x.shortname}))}/></Form.Item>
 <Form.Item name="profile_id" label="PPP Profile" rules={[{required:true}]}><Select options={(p.data??[]).map(x=>({value:x.id,label:x.name}))}/></Form.Item>
 <Form.Item name="static_ip" label="Статический IPv4 (пусто = пул)"><Input placeholder="10.216.71.240"/></Form.Item><Form.Item name="description" label="Описание"><Input maxLength={200}/></Form.Item>
 <Button type="primary" htmlType="submit" loading={a.busy} disabled={!eligible.length||!p.data?.length}>Создать пользователя</Button></Form>
 <Table<User> rowKey="id" loading={u.loading} dataSource={u.data??[]} columns={[{title:'Username',dataIndex:'username'},{title:'NAS',dataIndex:'nas'},{title:'PPP Profile',dataIndex:'profile'},{title:'IP / Pool',render:(_,x)=>x.static_ip??x.pool},{title:'Статус',render:(_,x)=><Tag color={x.enabled?'green':'red'}>{x.enabled?'Активен':'Отключён'}</Tag>},{title:'',render:(_,x)=><Space wrap><Button disabled={a.busy} onClick={()=>{passwordForm.resetFields();setTarget(x)}}>Пароль</Button><Popconfirm title="Изменить состояние VPN-пользователя? Активные сессии не завершаются автоматически." onConfirm={()=>a.run(()=>request('ppp/l2tp/users/'+x.id+'/state','PUT',{enabled:!x.enabled}))}><Button danger={x.enabled} disabled={a.busy}>{x.enabled?'Блокировать':'Включить'}</Button></Popconfirm></Space>}]}/>
 <Space><Button disabled={!offset||u.loading} onClick={()=>setOffset(v=>Math.max(0,v-100))}>Назад</Button><Button disabled={u.loading||(u.data?.length??0)<100} onClick={()=>setOffset(v=>v+100)}>Далее</Button></Space>
 </Disclosure><Modal title={'Смена пароля: '+(target?.username??'')} open={!!target} onCancel={()=>{passwordForm.resetFields();setTarget(undefined)}} onOk={()=>passwordForm.submit()} confirmLoading={a.busy}><Form form={passwordForm} layout="vertical" onFinish={v=>{if(target)return a.run(()=>request('ppp/l2tp/users/'+target.id+'/password','PUT',v),()=>{passwordForm.resetFields();setTarget(undefined)})}}><Form.Item name="password" label="Новый пароль" rules={[{required:true,min:16,max:128}]}><Input.Password autoComplete="new-password"/></Form.Item></Form></Modal></Space>
}
