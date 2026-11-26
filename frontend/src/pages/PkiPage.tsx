import React,{useEffect,useMemo,useState} from 'react';
import {Alert,App,Button,Card,Checkbox,Col,Form,Input,InputNumber,Modal,Popconfirm,Row,Select,Space,Table,Tag,Typography} from '../ui';
import {ReloadOutlined} from '../ui/icons';
import {type Request,type User,type Group,type Nas,type Session,type Audit,type Dashboard,type Attribute} from '../api';
import {StatCard} from '../vendor/design-kit/components/StatCard';
import MfaPanel from '../MfaPanel';
import {enc,useData,useAction,Fault} from '../hooks';
const {Text}=Typography;
type Certificate={fingerprint:string;purpose:string;subject:string;issuer:string;not_after:string;state:string};
export default function PkiPage({request}:{request:Request}){
 const d=useData<Certificate[]>(request,'pki/certificates');const a=useAction(d.refresh);const [form]=Form.useForm();
 return <Space direction="vertical" className="full"><Alert type="warning" message="PKI — реестр публичных сертификатов. EAP-TLS экспериментален и отключён по умолчанию. Применение отзыва к работающему серверу не подтверждено."/><Fault error={d.error}/><Card title="Импорт публичного сертификата"><Form form={form} layout="vertical" initialValues={{purpose:'client'}} onFinish={v=>a.run(()=>request('pki/certificates','POST',v),()=>form.resetFields())}><Form.Item name="purpose" label="Тип"><Select options={['ca','server','client'].map(x=>({value:x,label:x}))}/></Form.Item><Form.Item name="pem" label="PEM (только публичный сертификат)" rules={[{required:true}]}><Input.TextArea rows={5}/></Form.Item><Button type="primary" htmlType="submit" loading={a.busy}>Импортировать</Button></Form></Card><Table<Certificate> rowKey="fingerprint" loading={d.loading} dataSource={d.data??[]} scroll={{x:900}} columns={[{title:'Subject',dataIndex:'subject'},{title:'Issuer',dataIndex:'issuer'},{title:'Тип',dataIndex:'purpose'},{title:'Истекает',dataIndex:'not_after'},{title:'Статус',dataIndex:'state'},{title:'SHA256',render:(_,x)=><Text copyable>{x.fingerprint}</Text>},{title:'',render:(_,x)=><Popconfirm title="Отозвать сертификат в реестре?" onConfirm={()=>a.run(()=>request('pki/certificates/'+x.fingerprint+'/revoke','POST'))}><Button danger disabled={x.state==='revoked'||a.busy}>Отозвать</Button></Popconfirm>}]}/></Space>
}
