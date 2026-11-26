import {useState} from 'react';
import {Alert,Button,Checkbox,Form,Input,InputNumber,Select,Space} from '../ui';
import Disclosure from '../ui/Disclosure';
import {Fault} from '../hooks';
import type {Request,Nas} from '../api';
type Config={nas:string;sections:{name:string;commands:string}[];warnings:string[]};
function Generator({request,nas}:{request:Request;nas:Nas[]}){
 const [form]=Form.useForm();const [result,setResult]=useState<Config>();const [busy,setBusy]=useState(false);const [error,setError]=useState('');
 async function submit(v:Record<string,any>){setBusy(true);setError('');setResult(undefined);try{setResult(await request<Config>('ppp/routeros-config','POST',{...v,api_egress_ip:v.api_egress_ip||null,user_id:v.user_id||null}))}catch(e){setError(e instanceof Error?e.message:'Ошибка генерации')}finally{setBusy(false)}}
 function save(){if(!result)return;const url=URL.createObjectURL(new Blob([result.sections.map(s=>'# '+s.name+'\n'+s.commands).join('\n\n')+'\n'],{type:'text/plain;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='zradius-ppp-review.rsc';a.click();URL.revokeObjectURL(url)}
 return <Space direction="vertical" className="full"><Alert type="warning" message="Генератор только формирует команды для проверки. Все изменяющие команды закомментированы. Shared Secret не выводится."/><Fault error={error}/><Form form={form} layout="vertical" disabled={busy} initialValues={{interim_seconds:300,disconnect:false}} onFinish={submit}>
 <Form.Item name="nas_id" label="NAS" rules={[{required:true}]}><Select options={nas.map(n=>({value:n.id,label:n.shortname+' / '+n.nasname}))}/></Form.Item>
 <Form.Item name="radius_ip" label="IPv4 сервера RADIUS" rules={[{required:true}]}><Input placeholder="10.216.40.3"/></Form.Item>
 <Form.Item name="interim_seconds" label="Interim (сек)" rules={[{required:true}]}><InputNumber min={60} max={86400}/></Form.Item>
 <Form.Item name="disconnect" valuePropName="checked"><Checkbox>Добавить настройку Disconnect</Checkbox></Form.Item>
 <Form.Item name="api_egress_ip" label="IPv4 исходящего трафика API (для Disconnect)"><Input/></Form.Item>
 <Form.Item name="user_id" label="ID VPN-пользователя (необязательно)"><InputNumber min={1}/></Form.Item>
 <Button type="primary" htmlType="submit" disabled={!nas.length||busy} loading={busy}>Сформировать конфигурацию</Button></Form>
 {result&&<Space direction="vertical" className="full"><Alert type="warning" message={result.warnings.join(' ')}/><Button onClick={save}>Сохранить .rsc для проверки</Button>{result.sections.map(s=><Disclosure key={s.name} title={s.name} defaultOpen><Input.TextArea readOnly rows={Math.min(14,s.commands.split('\n').length+1)} value={s.commands}/></Disclosure>)}</Space>}</Space>
}
export default function RouterosPppConfig(props:{request:Request;nas:Nas[]}){return <Disclosure title="RouterOS Configuration Generator"><Generator {...props}/></Disclosure>}
