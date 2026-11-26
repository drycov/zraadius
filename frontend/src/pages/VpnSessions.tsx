import {useEffect,useState} from 'react';
import {App,Popconfirm,Alert,Button,Checkbox,Form,Input,Select,Space,Table,Tag} from '../ui';
import Disclosure from '../ui/Disclosure';
import {useData,Fault} from '../hooks';
import type {Request,Nas} from '../api';
type Session={radacctid:number;username:string;acctsessionid:string;nasipaddress:string;framedipaddress:string|null;acctstarttime:string|null;acctupdatetime:string|null;acctstoptime:string|null;acctsessiontime:number|null;acctinputoctets:number|null;acctoutputoctets:number|null;acctterminatecause:string|null;state:string};
type Command={id:number;radacctid:number;username:string;nasipaddress:string;acctsessionid:string;status:string;created_at:string;completed_at:string|null;acctstoptime:string|null};
type Capabilities={enabled:boolean;permitted:boolean};
type Summary={recorded:number;reported_open:number;no_update_15m:number};
function bytes(v:number|null){return v==null?'—':new Intl.NumberFormat('ru',{maximumFractionDigits:2}).format(v/1048576)+' MiB'}
function date(v:string|null){return v?new Date(v).toLocaleString():'—'}
function duration(v:number|null){return v==null?'—':Math.floor(v/3600)+'ч '+Math.floor(v%3600/60)+'м '+v%60+'с'}
function Sessions({request,nas}:{request:Request;nas:Nas[]}){
 const [form]=Form.useForm();const [filters,setFilters]=useState({active:true,username:'',nas:''});const [history,setHistory]=useState<number[]>([]);const [auto,setAuto]=useState(false);
 const params=new URLSearchParams({active:String(filters.active),limit:'101'});if(filters.username)params.set('username',filters.username);if(filters.nas)params.set('nas',filters.nas);if(history.length)params.set('before',String(history[history.length-1]));
 const d=useData<Session[]>(request,'ppp/sessions?'+params.toString());const summary=useData<Summary>(request,'ppp/session-summary');const refresh=()=>{d.refresh();summary.refresh()};
 useEffect(()=>{if(!auto)return;const t=window.setInterval(()=>{if(document.visibilityState==='visible')refresh()},30000);return()=>window.clearInterval(t)},[auto,filters,history,request]);
 const capabilities=useData<Capabilities>(request,'ppp/disconnect-capabilities');const commands=useData<Command[]>(request,'ppp/disconnect-history');const [busy,setBusy]=useState<number|null>(null);const {message}=App.useApp();
 async function disconnect(row:Session){
  setBusy(row.radacctid);
  try{const result=await request<{status:string}>('ppp/sessions/'+row.radacctid+'/disconnect','POST');if(result.status==='ack')message.success('NAS подтвердил Disconnect; ожидается Accounting-Stop');else message.warning('Disconnect: '+result.status)}
  catch(e){message.error(e instanceof Error?e.message:'Ошибка Disconnect')}
  finally{setBusy(null);refresh();commands.refresh()}
 }
 const rows=(d.data??[]).slice(0,100);
 return <Space direction="vertical" className="full"><Alert type="info" message="Только явно помеченные L2TP Accounting-записи. Отсутствие Stop не гарантирует доступность туннеля."/><Fault error={d.error||summary.error||capabilities.error||commands.error}/>{capabilities.data&&!capabilities.data.enabled&&<Alert type="warning" message="Disconnect отключён в конфигурации сервера (COA_ENABLED)."/>}
 <Space wrap><Tag>Записей: {summary.data?.recorded??'—'}</Tag><Tag>Без Stop: {summary.data?.reported_open??'—'}</Tag><Tag color="orange">Без обновления 15 мин: {summary.data?.no_update_15m??'—'}</Tag></Space>
 <Form form={form} layout="inline" initialValues={{active:true}} onFinish={v=>{setHistory([]);setFilters({active:!!v.active,username:v.username??'',nas:v.nas??''})}}><Form.Item name="active" valuePropName="checked"><Checkbox>Только без Stop</Checkbox></Form.Item><Form.Item name="username" label="Username"><Input maxLength={253}/></Form.Item><Form.Item name="nas" label="NAS"><Select allowClear options={nas.map(x=>({value:x.nasname,label:x.shortname+' / '+x.nasname}))}/></Form.Item><Button type="primary" htmlType="submit">Применить</Button><Button onClick={()=>{form.resetFields();setHistory([]);setFilters({active:true,username:'',nas:''})}}>Сбросить</Button></Form>
 <Space wrap><Button onClick={refresh}>Обновить</Button><Checkbox checked={auto} onChange={e=>setAuto(e.target.checked)}>Автообновление 30 сек</Checkbox></Space>
 <Table<Session> rowKey="radacctid" loading={d.loading} pagination={false} dataSource={rows} columns={[{title:'Username',dataIndex:'username'},{title:'NAS',dataIndex:'nasipaddress'},{title:'Remote IP',dataIndex:'framedipaddress'},{title:'Session ID',dataIndex:'acctsessionid'},{title:'Start',render:(_,x)=>date(x.acctstarttime)},{title:'Interim',render:(_,x)=>date(x.acctupdatetime)},{title:'Stop',render:(_,x)=>date(x.acctstoptime)},{title:'Длительность',render:(_,x)=>duration(x.acctsessiontime)},{title:'RX (NAS)',render:(_,x)=>bytes(x.acctinputoctets)},{title:'TX (NAS)',render:(_,x)=>bytes(x.acctoutputoctets)},{title:'Состояние',render:(_,x)=><Tag color={x.state==='stale'||x.state==='unknown'?'orange':x.state==='reported_open'?'green':undefined}>{({closed:'Закрыта',reported_open:'Без Stop',stale:'Устарела',unknown:'Неизвестно'} as Record<string,string>)[x.state]??x.state}</Tag>},{title:'Причина Stop',dataIndex:'acctterminatecause'},{title:'Действия',render:(_,x)=>!x.acctstoptime&&capabilities.data?.enabled&&capabilities.data.permitted?<Popconfirm title={'Завершить VPN-сессию '+x.username+' на '+x.nasipaddress+'?'} onConfirm={()=>disconnect(x)}><Button danger loading={busy===x.radacctid} disabled={busy!==null||d.loading}>Disconnect</Button></Popconfirm>:null}]}/>
 <Space><Button disabled={!history.length||d.loading} onClick={()=>setHistory(v=>v.slice(0,-1))}>Назад</Button><Button disabled={d.loading||(d.data?.length??0)<=100} onClick={()=>setHistory(v=>[...v,rows[rows.length-1].radacctid])}>Далее</Button></Space><Disclosure title="Журнал Disconnect"><Button onClick={commands.refresh}>Обновить журнал</Button><Table<Command> rowKey="id" loading={commands.loading} dataSource={commands.data??[]} columns={[{title:'ID',dataIndex:'id'},{title:'Username',dataIndex:'username'},{title:'NAS',dataIndex:'nasipaddress'},{title:'Session ID',dataIndex:'acctsessionid'},{title:'Результат',render:(_,x)=><Tag color={x.status==='ack'?'green':x.status==='nak'?'red':'orange'}>{x.status.toUpperCase()}</Tag>},{title:'Запрос',render:(_,x)=>date(x.created_at)},{title:'Ответ',render:(_,x)=>date(x.completed_at)},{title:'Accounting Stop',render:(_,x)=>date(x.acctstoptime)}]}/></Disclosure></Space>
}
export default function VpnSessions(props:{request:Request;nas:Nas[]}){
 return <Disclosure title="Active VPN Sessions / Accounting"><Sessions {...props}/></Disclosure>
}
