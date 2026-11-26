import {Alert,Button,Form,Input,Select,Space,Table,Popconfirm} from '../ui';
import Disclosure from '../ui/Disclosure';
import {useData,useAction,Fault} from '../hooks';
import type {Request,Nas} from '../api';
import type {AddressSpace} from './VpnAddressSpaces';
type Pool={id:number;name:string;nas:string;address_space:string;network:string;first_ip:string;last_ip:string;capacity:number};
export default function VpnPools({request,nas,spaces}:{request:Request;nas:Nas[];spaces:AddressSpace[]}){
 const d=useData<Pool[]>(request,'ppp/pools');const a=useAction(d.refresh);const [form]=Form.useForm();
 return <Disclosure title="Dynamic IP Pools" meta={String(d.data?.length??0)}><Space direction="vertical"><Alert type="warning" message="Реестр диапазонов RouterOS. Ёмкость не равна количеству свободных адресов. Изменения не отправляются на NAS."/><Fault error={d.error}/><Form form={form} layout="inline" onFinish={v=>a.run(()=>request('ppp/pools','POST',v),()=>form.resetFields())}>
 <Form.Item name="name" label="Имя пула" rules={[{required:true}]}><Input placeholder="Satory_VPN_2"/></Form.Item>
 <Form.Item name="nas_id" label="NAS" rules={[{required:true}]}><Select options={nas.map(x=>({value:x.id,label:x.shortname}))}/></Form.Item>
 <Form.Item name="address_space_id" label="Address Space" rules={[{required:true}]}><Select options={spaces.map(x=>({value:x.id,label:x.name}))}/></Form.Item>
 <Form.Item name="network" label="IPv4 CIDR" rules={[{required:true}]}><Input placeholder="10.216.71.0/24"/></Form.Item>
 <Form.Item name="first_ip" label="Начальный IP" rules={[{required:true}]}><Input/></Form.Item>
 <Form.Item name="last_ip" label="Конечный IP" rules={[{required:true}]}><Input/></Form.Item>
 <Button type="primary" htmlType="submit" disabled={!nas.length||!spaces.length} loading={a.busy}>Зарегистрировать пул</Button></Form>
 <Table<Pool> rowKey="id" loading={d.loading} dataSource={d.data??[]} columns={[{title:'Pool',dataIndex:'name'},{title:'NAS',dataIndex:'nas'},{title:'Address Space',dataIndex:'address_space'},{title:'CIDR',dataIndex:'network'},{title:'Диапазон',render:(_,x)=>x.first_ip+' – '+x.last_ip},{title:'Ёмкость',dataIndex:'capacity'},{title:'',render:(_,x)=><Popconfirm title="Удалить запись реестра? Пул RouterOS не изменится." onConfirm={()=>a.run(()=>request('ppp/pools/'+x.id,'DELETE'))}><Button danger disabled={a.busy}>Удалить</Button></Popconfirm>}]}/></Space></Disclosure>
}
