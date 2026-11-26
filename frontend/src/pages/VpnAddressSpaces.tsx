import {Alert,Button,Form,Input,Space,Table} from '../ui';
import Disclosure from '../ui/Disclosure';
import {useData,useAction,Fault} from '../hooks';
import type {Request} from '../api';
export type AddressSpace={id:number;name:string;description:string;members:number};
type Conflict={static_ip:string;assignments:number;usernames:string[]};
export default function VpnAddressSpaces({request,items,loading,refresh}:{request:Request;items:AddressSpace[];loading:boolean;refresh:()=>void}){
 const c=useData<Conflict[]>(request,'ppp/address-spaces/conflicts');const a=useAction(()=>{refresh();c.refresh()});const [form]=Form.useForm();
 return <Disclosure title="VPN Address Spaces" meta={String(items.length)}><Space direction="vertical"><Alert type="warning" message="Общее пространство контролирует уникальность статических IPv4 между NAS. VRF на маршрутизаторах настраивается отдельно. Без пространства действует прежняя проверка на NAS."/><Fault error={c.error}/><Form form={form} layout="inline" onFinish={v=>a.run(()=>request('ppp/address-spaces','POST',v),()=>form.resetFields())}><Form.Item name="name" label="Адресное пространство" rules={[{required:true,max:64}]}><Input placeholder="VRF-MANAGEMENT"/></Form.Item><Form.Item name="description" label="Описание"><Input maxLength={200}/></Form.Item><Button type="primary" htmlType="submit" loading={a.busy}>Создать</Button></Form><Table<AddressSpace> rowKey="id" dataSource={items} loading={loading} columns={[{title:'Address Space',dataIndex:'name'},{title:'Описание',dataIndex:'description'},{title:'Назначения',dataIndex:'members'}]}/><Button onClick={c.refresh}>Проверить повторяющиеся IP</Button><Table<Conflict> rowKey="static_ip" dataSource={c.data??[]} loading={c.loading} columns={[{title:'IPv4 (требует проверки)',dataIndex:'static_ip'},{title:'Назначения',dataIndex:'assignments'},{title:'Пользователи',render:(_,x)=>x.usernames.join(', ')}]}/></Space></Disclosure>
}
