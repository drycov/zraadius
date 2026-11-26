import {useState} from 'react';
import {Alert,Button,Form,Input,Select,Space,Table,Popconfirm} from '../ui';
import Disclosure from '../ui/Disclosure';
import {useData,useAction,Fault} from '../hooks';
import type {Request} from '../api';
type Group={id:number;name:string;description:string;device_group_ids:number[];members:number};
type DeviceGroup={id:number;name:string};
function Binding({request,group,options,refresh}:{request:Request;group:Group;options:DeviceGroup[];refresh:()=>void}){
 const [ids,setIds]=useState(group.device_group_ids);const a=useAction(refresh);
 return <Space direction="vertical" className="full"><Select mode="multiple" value={ids} onChange={setIds} options={options.map(x=>({value:x.id,label:x.name}))}/><Popconfirm title="Изменить наследуемые разрешения всех членов группы?" onConfirm={()=>a.run(()=>request('identities/groups/'+group.id+'/bindings','PUT',{device_group_ids:ids}))}><Button type="primary" loading={a.busy}>Сохранить привязки</Button></Popconfirm></Space>
}
export default function IdentityGroups({request}:{request:Request}){
 const d=useData<Group[]>(request,'identities/groups');const g=useData<DeviceGroup[]>(request,'device-aaa/groups');const [form]=Form.useForm();const a=useAction(d.refresh);
 return <Disclosure title="Глобальные группы пользователей"><Space direction="vertical" className="full"><Fault error={d.error||g.error}/><Alert type="info" message="Группа наследует политики Device AAA. Сервис Device AAA должен быть отдельно включён у пользователя. VPN пока назначается индивидуально."/><Form form={form} layout="inline" onFinish={v=>a.run(()=>request('identities/groups','POST',{name:v.name,description:v.description??''}),()=>form.resetFields())}><Form.Item name="name" label="Группа" rules={[{required:true,max:64}]}><Input/></Form.Item><Form.Item name="description" label="Описание"><Input maxLength={200}/></Form.Item><Button type="primary" htmlType="submit" loading={a.busy}>Создать группу</Button></Form>{(d.data??[]).map(x=><Disclosure key={x.id} title={x.name} description={x.description} meta={'Участников: '+x.members}>{g.data&&<Binding request={request} group={x} options={g.data} refresh={d.refresh}/>}</Disclosure>)}</Space></Disclosure>
}
type Effective={nas_id:number;shortname:string;role:string;filter_id:string|null;source:string};
function Membership({request,id,groups,initial,refresh}:{request:Request;id:number;groups:Group[];initial:number[];refresh:()=>void}){
 const [ids,setIds]=useState(initial);const a=useAction(refresh);
 return <Space direction="vertical" className="full"><Select mode="multiple" value={ids} onChange={setIds} options={groups.map(g=>({value:g.id,label:g.name}))}/><Popconfirm title="Изменить членство и наследуемые разрешения?" onConfirm={()=>a.run(()=>request('identities/'+id+'/groups','PUT',{group_ids:ids}))}><Button type="primary" loading={a.busy}>Сохранить членство</Button></Popconfirm></Space>
}
export function IdentityMembership({request,id}:{request:Request;id:number}){
 const g=useData<Group[]>(request,'identities/groups');const d=useData<{group_ids:number[]}>(request,'identities/'+id+'/groups');const e=useData<Effective[]>(request,'identities/'+id+'/effective-device-grants');
 return <Disclosure title="Глобальные группы и эффективный доступ"><Space direction="vertical" className="full"><Fault error={g.error||d.error||e.error}/>{g.data&&d.data&&<Membership request={request} id={id} groups={g.data} initial={d.data.group_ids} refresh={()=>{d.refresh();e.refresh()}}/>}<Button onClick={e.refresh}>Обновить эффективные права</Button><Table<Effective> rowKey="nas_id" loading={e.loading} dataSource={e.data??[]} columns={[{title:'NAS',dataIndex:'shortname'},{title:'Role',dataIndex:'role'},{title:'Filter-Id',dataIndex:'filter_id'},{title:'Источник',dataIndex:'source'}]}/></Space></Disclosure>
}
