import {useState} from 'react';
import {Alert,Button,Input,Select,Space,Table} from '../ui';
import {useData,useAction,Fault} from '../hooks';
import type {Request} from '../api';
type Entry={name:string;vendor:number;type:string;list:string;lists:string[];operators:Record<string,string[]>;runtime_enforced:boolean};
type Result={name:string;list:string;operator:string;value:string;vendor:number;runtime_enforced:boolean};
export default function Dictionary({request}:{request:Request}){
 const d=useData<Entry[]>(request,'dictionaries');const a=useAction(()=>{});
 const [name,setName]=useState('');const [list,setList]=useState('reply');const [op,setOp]=useState(':=');const [value,setValue]=useState('');const [result,setResult]=useState<Result|null>(null);const [query,setQuery]=useState('');
 const selected=d.data?.find(x=>x.name===name);
 const reset=()=>setResult(null);
 return <Space direction="vertical" className="full"><Fault error={d.error}/><Alert type="info" message="Типизированный каталог для проектирования RADIUS-политик. Проверка не изменяет runtime FreeRADIUS и не сохраняет назначения."/>
 <Input value={query} placeholder="Поиск атрибута" onChange={e=>setQuery(e.target.value)}/>
 <Table<Entry> rowKey="name" loading={d.loading} dataSource={(d.data??[]).filter(x=>x.name.toLowerCase().includes(query.toLowerCase()))} columns={[{title:'Атрибут',dataIndex:'name'},{title:'Vendor ID',dataIndex:'vendor'},{title:'Тип',dataIndex:'type'},{title:'List',dataIndex:'list'},{title:'Операторы',render:(_,x)=>x.operators[x.list].join(', ')}]}/>
 <label>Атрибут<Select value={name||undefined} options={(d.data??[]).map(x=>({value:x.name,label:x.name}))} onChange={v=>{const next=d.data?.find(x=>x.name===v);setName(String(v));setList(next?.list??'reply');setOp(next?.operators[next.list]?.[0]??':=');setValue('');reset()}}/></label>
 <label>List<Select value={list} options={(selected?.lists??[]).map(x=>({value:x,label:x}))} onChange={v=>{setList(String(v));setOp(selected?.operators[String(v)]?.[0]??':=');reset()}}/></label>
 <label>Operator<Select value={op} options={(selected?.operators[list]??[]).map(x=>({value:x,label:x}))} onChange={v=>{setOp(String(v));reset()}}/></label>
 <label>Value<Input value={value} maxLength={253} onChange={e=>{setValue(e.target.value);reset()}}/></label>
 <Button type="primary" disabled={!selected||!value||a.busy} loading={a.busy} onClick={()=>a.run(async()=>{reset();setResult(await request<Result>('dictionaries/validate','POST',{name,attribute_list:list,operator:op,value}))})}>Проверить атрибут</Button>
 {result&&<><Alert type="success" message="Атрибут валиден для планирования. Runtime не изменён."/><pre>{JSON.stringify(result,null,2)}</pre></>}
 </Space>
}
