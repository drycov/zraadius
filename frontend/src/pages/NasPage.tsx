import React,{useEffect,useMemo,useState} from 'react';
import {Alert,App,Button,Card,Checkbox,Col,Form,Input,InputNumber,Modal,Popconfirm,Row,Select,Space,Table,Tag,Typography} from '../ui';
import {ReloadOutlined} from '../ui/icons';
import {type Request,type User,type Group,type Nas,type Session,type Audit,type Dashboard,type Attribute} from '../api';
import {StatCard} from '../vendor/design-kit/components/StatCard';
import MfaPanel from '../MfaPanel';
import {enc,useData,useAction,Fault} from '../hooks';
const {Text}=Typography;
export default function NasPage({request}:{request:Request}){
 const d=useData<Nas[]>(request,'nas');const a=useAction(d.refresh);const [form]=Form.useForm();
 return <Space direction="vertical" className="full"><Alert type="warning" showIcon message="NAS: для применения изменений требуется включить RADIUS_ENABLE_NAS и перезапустить radius."/><Fault error={d.error}/><Card title="Добавить NAS"><Form form={form} layout="vertical" initialValues={{vendor:'mikrotik'}} onFinish={v=>a.run(()=>request('nas','POST',v),()=>form.resetFields())}><Row gutter={12}><Col xs={24} md={8}><Form.Item name="address" label="IP" rules={[{required:true}]}><Input/></Form.Item></Col><Col xs={24} md={8}><Form.Item name="name" label="Имя" rules={[{required:true}]}><Input/></Form.Item></Col><Col xs={24} md={8}><Form.Item name="vendor" label="Производитель"><Select options={['mikrotik','cisco','other'].map(v=>({label:v,value:v}))}/></Form.Item></Col></Row><Form.Item name="secret" label="Shared Secret" rules={[{required:true,min:32}]}><Input.Password/></Form.Item><Form.Item name="description" label="Описание"><Input/></Form.Item><Button type="primary" htmlType="submit" loading={a.busy}>Добавить</Button></Form></Card><Table<Nas> rowKey="id" loading={d.loading} dataSource={d.data??[]} scroll={{x:600}} columns={[{title:'Имя',dataIndex:'shortname'},{title:'IP',dataIndex:'nasname'},{title:'Тип',dataIndex:'type'},{title:'Описание',dataIndex:'description'},{title:'',render:(_,n)=><Popconfirm title="Удалить NAS из реестра?" onConfirm={()=>a.run(()=>request('nas/'+n.id,'DELETE'))}><Button danger disabled={a.busy}>Удалить</Button></Popconfirm>}]}/></Space>
}
