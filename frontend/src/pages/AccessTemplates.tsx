import {useState} from 'react';
import {Alert,Button,Checkbox,Input,Select,Space,Table,Tag} from '../ui';
import {useAction,useData,Fault} from '../hooks';
import type {Request} from '../api';
export const serviceCodes=['device-aaa','l2tp','pppoe','hotspot','dot1x','wpa-enterprise','console'] as const;
export type AccessTemplate={id:number;name:string;account_type:'person'|'service';description:string;services:string[];enabled:boolean};
export default function AccessTemplates({request,refresh}:{request:Request;refresh:()=>void}){
 const path='identities/access-templates';
 const d=useData<AccessTemplate[]>(request,path);
 const a=useAction(()=>{d.refresh();refresh()});
 const [editing,setEditing]=useState<number>();
 const [name,setName]=useState('');const [description,setDescription]=useState('');const [kind,setKind]=useState<'person'|'service'>('person');const [services,setServices]=useState<string[]>([]);const [enabled,setEnabled]=useState(true);
 const reset=()=>{setEditing(undefined);setName('');setDescription('');setKind('person');setServices([]);setEnabled(true)};
 return <Space direction="vertical" className="full">
 <Alert type="info" message="Шаблон заполняет форму создания УЗ. Не предоставляет доступ сам по себе и не изменяет существующие назначения."/>
 <Fault error={d.error}/>
 <Table<AccessTemplate> rowKey="id" loading={d.loading} dataSource={d.data??[]} columns={[{title:'Шаблон',dataIndex:'name'},{title:'Тип',dataIndex:'account_type'},{title:'Услуги',render:(_,r)=><Space wrap>{r.services.map(s=><Tag key={s}>{s}</Tag>)}</Space>},{title:'Состояние',render:(_,r)=><Tag color={r.enabled?'green':'red'}>{r.enabled?'Активен':'Отключён'}</Tag>},{title:'Действия',render:(_,r)=><Button disabled={a.busy} onClick={()=>{setEditing(r.id);setName(r.name);setDescription(r.description);setKind(r.account_type);setServices(r.services);setEnabled(r.enabled)}}>Изменить</Button>}]}/>
 <label>Название<Input value={name} maxLength={100} onChange={e=>setName(e.target.value)}/></label>
 <label>Описание<Input value={description} maxLength={500} onChange={e=>setDescription(e.target.value)}/></label>
 <Select value={kind} onChange={v=>{setKind(v==='service'?'service':'person');if(v==='service')setServices(old=>old.filter(s=>s!=='console'))}} options={[{value:'person',label:'Персональная УЗ'},{value:'service',label:'Сервисная УЗ'}]}/>
 <Space wrap>{serviceCodes.map(s=><Checkbox key={s} disabled={a.busy||(kind==='service'&&s==='console')} checked={services.includes(s)} onChange={e=>setServices(old=>e.target.checked?[...old,s]:old.filter(x=>x!==s))}>{s}</Checkbox>)}</Space>
 <Checkbox checked={enabled} onChange={e=>setEnabled(e.target.checked)}>Активный шаблон</Checkbox>
 <Space wrap><Button type="primary" disabled={!name.trim()||a.busy} onClick={()=>a.run(()=>request(editing?path+'/'+editing:path,editing?'PUT':'POST',{name,description,account_type:kind,services,enabled}),reset)}>{editing?'Сохранить':'Создать шаблон'}</Button><Button disabled={a.busy} onClick={reset}>Сбросить</Button></Space>
 </Space>
}
