import React,{useEffect,useMemo,useState} from 'react';
import {Alert,App,Button,Card,Checkbox,Col,Form,Input,InputNumber,Modal,Popconfirm,Row,Select,Space,Table,Tag,Typography} from '../ui';
import {ReloadOutlined} from '../ui/icons';
import {type Request,type User,type Group,type Nas,type Session,type Audit,type Dashboard,type Attribute} from '../api';
import {StatCard} from '../vendor/design-kit/components/StatCard';
import MfaPanel from '../MfaPanel';
import {enc,useData,useAction,Fault} from '../hooks';
const {Text}=Typography;
type AdminSession={session_id:string;username:string;created_at:string;expires_at:string};
export default function AccountPage({request}:{request:Request}){
 const d=useData<(AdminSession&{current:boolean})[]>(request,'iam/my-sessions');const a=useAction(d.refresh);const [form]=Form.useForm();
 return <Space direction="vertical" className="full"><Fault error={d.error}/><Card title="Смена собственного пароля"><Form form={form} layout="vertical" onFinish={v=>a.run(()=>request('iam/password','PUT',v),()=>{form.resetFields();window.location.reload()})}><Form.Item name="current_password" label="Текущий пароль" rules={[{required:true}]}><Input.Password autoComplete="current-password"/></Form.Item><Form.Item name="password" label="Новый пароль" rules={[{required:true,min:16,max:128}]}><Input.Password autoComplete="new-password"/></Form.Item><Button htmlType="submit" type="primary" loading={a.busy}>Сменить пароль и выйти</Button></Form></Card><MfaPanel request={request}/><Card title="Мои сессии"><Table rowKey="session_id" dataSource={d.data??[]} loading={d.loading} columns={[{title:'Создана',dataIndex:'created_at'},{title:'Истекает',dataIndex:'expires_at'},{title:'Текущая',render:(_,x)=>x.current?'Да':'Нет'}]}/></Card></Space>
}
