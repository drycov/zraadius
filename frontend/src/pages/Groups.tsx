import Tabs from '../ui/Tabs';
import IdentityGroups from './IdentityGroups';
import React,{useEffect,useMemo,useState} from 'react';
import {Alert,App,Button,Card,Checkbox,Col,Form,Input,InputNumber,Modal,Popconfirm,Row,Select,Space,Table,Tag,Typography} from '../ui';
import {ReloadOutlined} from '../ui/icons';
import {type Request,type User,type Group,type Nas,type Session,type Audit,type Dashboard,type Attribute} from '../api';
import {StatCard} from '../vendor/design-kit/components/StatCard';
import MfaPanel from '../MfaPanel';
import {GroupList} from '../ui/Disclosure';
import {enc,useData,useAction,Fault} from '../hooks';
const {Text}=Typography;
function GroupProfile({request,group}:{request:Request;group:string}){
 const profile=useData<{attribute:string;op:string;value:string}[]>(request,'groups/'+enc(group)+'/profile');const a=useAction(profile.refresh);const [form]=Form.useForm();
 return <Space direction="vertical" className="full"><Fault error={profile.error}/><Table rowKey="attribute" size="small" pagination={false} loading={profile.loading} dataSource={profile.data??[]} columns={[{title:'Атрибут',dataIndex:'attribute'},{title:'Оператор',dataIndex:'op'},{title:'Значение',dataIndex:'value'}]}/><Form form={form} layout="vertical" initialValues={{download_mbps:100,upload_mbps:100,interim_seconds:300,idle_seconds:3600}} onFinish={v=>a.run(()=>request('groups/'+enc(group)+'/mikrotik-profile','PUT',{...v,pool:v.pool||null}))}><Row gutter={16}>{[['download_mbps','Download Мбит/с',1,100000],['upload_mbps','Upload Мбит/с',1,100000],['interim_seconds','Interim, сек',60,86400],['idle_seconds','Idle, сек',0,86400]].map(([key,label,min,max])=><Col xs={12} md={6} key={key}><Form.Item name={String(key)} label={String(label)} rules={[{required:true}]}><InputNumber min={Number(min)} max={Number(max)} className="full"/></Form.Item></Col>)}</Row><Form.Item name="pool" label="Framed-Pool"><Input/></Form.Item><Alert type="warning" message="Сохранение заменяет текущий профиль группы."/><Button type="primary" htmlType="submit" loading={a.busy}>Применить профиль</Button></Form></Space>
}

function LegacyGroups({request}:{request:Request}){
 const d=useData<Group[]>(request,'groups');const a=useAction(d.refresh);const [create]=Form.useForm();
 return <Card title="Группы абонентов"><Fault error={d.error}/><Space direction="vertical" className="full"><Form form={create} layout="inline" onFinish={v=>a.run(()=>request('groups','POST',v),()=>create.resetFields())}><Form.Item name="name" label="Название группы" rules={[{required:true}]}><Input placeholder="INTERNET-100M"/></Form.Item><Button type="primary" htmlType="submit" loading={a.busy}>Создать</Button></Form><GroupList items={(d.data??[]).map(x=>({...x,id:x.name}))} loading={d.loading} render={x=><GroupProfile key={x.name} request={request} group={x.name}/>}/></Space></Card>
}

export default function Groups({request}:{request:Request}){
 return <Tabs label="Единый центр групп" items={[
 {id:'identity-groups',label:'Глобальные группы',content:<IdentityGroups request={request}/>},
 {id:'legacy-groups',label:'Legacy RADIUS группы',content:<><Alert type="warning" message="Совместимость с существующими абонентскими группами. Для новых персональных и сервисных УЗ используйте глобальные группы."/><LegacyGroups request={request}/></>}
 ]}/>
}
