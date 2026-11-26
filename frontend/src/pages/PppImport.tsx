import {useState} from 'react';
import {Alert,Button,Input,Select,Space,Table,Popconfirm,Tag} from '../ui';
import Disclosure from '../ui/Disclosure';
import {Fault} from '../hooks';
import type {Request,Nas} from '../api';
import type {AddressSpace} from './VpnAddressSpaces';
type Row={line:number;kind:string;name:string;issues:string[];action?:string;warning?:string;profile?:string;static_ip?:string};
type Preview={rows:Row[];can_apply:boolean};
function ImportForm({request,nas,spaces,refresh}:{request:Request;nas:Nas[];spaces:AddressSpace[];refresh:()=>void}){
 const [source,setSource]=useState('');const [nasId,setNasId]=useState<number>();const [space,setSpace]=useState<number>();const [preview,setPreview]=useState<Preview>();const [busy,setBusy]=useState(false);const [error,setError]=useState('');const [result,setResult]=useState('');
 const body={export:source,nas_id:nasId,address_space_id:space??null};
 async function run(apply:boolean){setBusy(true);setError('');setResult('');try{if(apply){const r=await request<{profiles:number;users_disabled:number}>('ppp/import/apply','POST',body);setResult('Профилей создано: '+r.profiles+'; отключённых пользователей: '+r.users_disabled);setPreview(undefined);setSource('');refresh()}else setPreview(await request<Preview>('ppp/import/preview','POST',body))}catch(e){setError(e instanceof Error?e.message:'Ошибка импорта');setPreview(undefined)}finally{setBusy(false)}}
 return <Space direction="vertical" className="full"><Alert type="warning" message="Используйте экспорт без паролей. Только service=l2tp. Все новые пользователи создаются отключёнными; задайте новый пароль и включите вручную. RouterOS не изменяется."/><Fault error={error}/>{result&&<Alert type="success" message={result}/>}
 <label>NAS</label><Select disabled={busy} value={nasId} onChange={v=>{setNasId(v);setPreview(undefined)}} options={nas.map(x=>({value:x.id,label:x.shortname}))}/>
 <label>Address Space</label><Select disabled={busy} allowClear value={space} onChange={v=>{setSpace(v);setPreview(undefined)}} options={spaces.map(x=>({value:x.id,label:x.name}))}/>
 <label>RouterOS .rsc (без секретов)</label><Input.TextArea rows={10} maxLength={262144} disabled={busy} value={source} onChange={e=>{setSource(e.target.value);setPreview(undefined)}} placeholder="/ppp profile"/>
 <Space wrap><Button type="primary" loading={busy} disabled={!nasId||!source.trim()||busy} onClick={()=>run(false)}>Dry Run</Button><Popconfirm title="Создать профили и отключённых VPN-пользователей? Существующие записи не перезаписываются." onConfirm={()=>run(true)}><Button disabled={busy||!preview?.can_apply}>Импортировать</Button></Popconfirm></Space>
 {preview&&<Table<Row> rowKey="line" dataSource={preview.rows} columns={[{title:'Строка',dataIndex:'line'},{title:'Тип',dataIndex:'kind'},{title:'Имя',dataIndex:'name'},{title:'Профиль',dataIndex:'profile'},{title:'IPv4',dataIndex:'static_ip'},{title:'Действие',render:(_,x)=><Tag color={x.issues.length?'red':'green'}>{x.issues.length?'Конфликт':x.action??'—'}</Tag>},{title:'Проверка',render:(_,x)=>[...x.issues,x.warning].filter(Boolean).join('; ')}]}/>}</Space>
}
export default function PppImport(props:{request:Request;nas:Nas[];spaces:AddressSpace[];refresh:()=>void}){return <Disclosure title="MikroTik PPP Import / Dry Run"><ImportForm {...props}/></Disclosure>}
