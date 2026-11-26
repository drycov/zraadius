import React,{useEffect,useMemo,useState} from 'react';
import {Alert,App,Button,Card,Checkbox,Col,Form,Input,InputNumber,Modal,Popconfirm,Row,Select,Space,Table,Tag,Typography} from '../ui';
import {ReloadOutlined} from '../ui/icons';
import {type Request,type User,type Group,type Nas,type Session,type Audit,type Dashboard,type Attribute} from '../api';
import {StatCard} from '../vendor/design-kit/components/StatCard';
import MfaPanel from '../MfaPanel';
import {enc,useData,useAction,Fault} from '../hooks';
const {Text}=Typography;
type ServiceItem={code:string;name:string;methods:string;maturity:string};
export default function ServicesPage({request}:{request:Request}){
 const d=useData<ServiceItem[]>(request,'services');
 const n=useData<Nas[]>(request,'nas');const g=useData<Group[]>(request,'groups');
 const [kind,setKind]=useState('nas');const [target,setTarget]=useState('');const [selected,setSelected]=useState<string[]>([]);const [loaded,setLoaded]=useState(false);const [busy,setBusy]=useState(false);const {message}=App.useApp();
 const path=()=>kind+'/'+enc(target)+'/services';
 return <Space direction="vertical" className="full"><Alert type="warning" showIcon message="Каталог и привязки сервисов — метаданные. Политики пока не применяются FreeRADIUS."/><Fault error={d.error||n.error||g.error}/><Table<ServiceItem> rowKey="code" loading={d.loading} dataSource={d.data??[]} pagination={false} columns={[{title:'Сервис',dataIndex:'name'},{title:'Методы',dataIndex:'methods'},{title:'Готовность',render:(_,s)=><Tag>{s.maturity}</Tag>}]}/><Card title="Привязка сервисов"><Space wrap><Select value={kind} disabled={busy} options={[{value:'nas',label:'NAS'},{value:'groups',label:'Группа'}]} onChange={v=>{setKind(v);setTarget('');setLoaded(false);setSelected([])}}/><Select style={{minWidth:220}} placeholder="Выберите объект" value={target||undefined} disabled={busy} options={kind==='nas'?(n.data??[]).map(x=>({value:String(x.id),label:x.shortname})):(g.data??[]).map(x=>({value:x.name,label:x.name}))} onChange={v=>{setTarget(v);setLoaded(false);setSelected([])}}/><Button disabled={!target||busy} onClick={async()=>{setBusy(true);setLoaded(false);try{const r=await request<{services:string[]}>(path());setSelected(r.services);setLoaded(true)}catch(e){message.error(String(e))}finally{setBusy(false)}}}>Загрузить</Button></Space><div style={{marginTop:16}}><Select mode="multiple" style={{width:'100%'}} disabled={!loaded||busy} value={selected} onChange={setSelected} options={(d.data??[]).map(x=>({value:x.code,label:x.name}))}/></div><Button style={{marginTop:16}} type="primary" disabled={!loaded||busy} loading={busy} onClick={async()=>{setBusy(true);try{await request(path(),'PUT',{services:selected});message.success('Привязки сохранены, runtime не изменён')}catch(e){message.error(String(e))}finally{setBusy(false)}}}>Сохранить</Button></Card></Space>
}
