import {useState} from 'react';
import {Alert,Button,Space,Table,Tag} from '../ui';
import {useAction} from '../hooks';
import type {Request} from '../api';
type Entry={username:string;full_name:string;department:string;directory_enabled:boolean;compatible:boolean;local_exists:boolean};
type Result={items:Entry[];limited:boolean};
export default function IdentityDirectory({request}:{request:Request}){
 const [result,setResult]=useState<Result>();const a=useAction(()=>{});
 return <Space direction="vertical" className="full"><Alert type="info" message="Только чтение Active Directory через LDAPS. Импорт, синхронизация паролей и внешняя авторизация пока не выполняются."/><Button loading={a.busy} onClick={()=>a.run(async()=>{setResult(undefined);setResult(await request<Result>('identities/directory-preview'))})}>Проверить каталог AD</Button>{result?.limited&&<Alert type="warning" message="Выборка ограничена 200 записями."/>}<Table<Entry> rowKey="username" dataSource={result?.items??[]} columns={[{title:'Логин',dataIndex:'username'},{title:'ФИО',dataIndex:'full_name'},{title:'Подразделение',dataIndex:'department'},{title:'AD',render:(_,r)=><Tag color={r.directory_enabled?'green':'red'}>{r.directory_enabled?'Активен':'Отключён / неизвестно'}</Tag>},{title:'Unified Identity',render:(_,r)=>r.local_exists?'Существует':r.compatible?'Кандидат':'Несовместимый логин'}]}/></Space>
}
