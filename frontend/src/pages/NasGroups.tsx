import Disclosure,{GroupList} from '../ui/Disclosure';
import {Alert,Button,Card,Form,Input,Popconfirm,Select,Space,Table,Tag} from '../ui';
import {useAction,useData,Fault} from '../hooks';
import type {Request,Nas} from '../api';
type Group={id:number;name:string;description:string};
type Member=Nas&{explicit:boolean};
type Network={network:string};
function Details({request,group,nas}:{request:Request;group:Group;nas:Nas[]}){
 const path='nas/groups/'+group.id;const m=useData<Member[]>(request,path+'/members');const n=useData<Network[]>(request,path+'/networks');const a=useAction(()=>{m.refresh();n.refresh()});const [mf]=Form.useForm();const [nf]=Form.useForm();
 return <Space direction="vertical" className="full"><Fault error={m.error||n.error}/><Alert type="warning" message="CIDR включает только зарегистрированные NAS. Новые совпадающие NAS автоматически наследуют групповые разрешения."/>
 <Disclosure title="Добавить оборудование"><Form form={mf} layout="inline" onFinish={v=>a.run(()=>request(path+'/members/'+v.nas_id,'PUT'),()=>mf.resetFields())}><Form.Item name="nas_id" label="NAS" rules={[{required:true}]}><Select options={nas.filter(x=>!(m.data??[]).some(y=>y.id===x.id&&y.explicit)).map(x=>({value:x.id,label:x.shortname+' / '+x.nasname}))}/></Form.Item><Button type="primary" htmlType="submit" loading={a.busy}>Добавить NAS</Button></Form></Disclosure>
 <Disclosure title="Сетевые селекторы CIDR" meta={n.loading?'…':String(n.data?.length??0)}><Form form={nf} layout="inline" onFinish={v=>a.run(()=>request(path+'/networks','POST',v),()=>nf.resetFields())}><Form.Item name="network" label="CIDR" rules={[{required:true}]}><Input placeholder="10.216.0.0/16"/></Form.Item><Popconfirm title="Добавить все зарегистрированные NAS этой сети в группу?" onConfirm={()=>nf.submit()}><Button type="primary" loading={a.busy}>Добавить сеть</Button></Popconfirm></Form>
 <Table<Network> rowKey="network" dataSource={n.data??[]} loading={n.loading} columns={[{title:'CIDR',dataIndex:'network'},{title:'',render:(_,x)=><Popconfirm title="Удалить сетевой селектор?" onConfirm={()=>a.run(()=>request(path+'/networks/'+x.network,'DELETE'))}><Button danger disabled={a.busy}>Удалить</Button></Popconfirm>}]}/></Disclosure>
 <Disclosure title="Участники NAS" meta={m.loading?'…':String(m.data?.length??0)} defaultOpen><Table<Member> rowKey="id" dataSource={m.data??[]} loading={m.loading} columns={[{title:'NAS',dataIndex:'shortname'},{title:'IP',dataIndex:'nasname'},{title:'Источник',render:(_,x)=><Tag>{x.explicit?'Индивидуальный (возможен также CIDR)':'CIDR'}</Tag>},{title:'',render:(_,x)=>x.explicit?<Popconfirm title="Удалить явное членство? Совпадение по CIDR может сохранить доступ." onConfirm={()=>a.run(()=>request(path+'/members/'+x.id,'DELETE'))}><Button danger disabled={a.busy}>Удалить</Button></Popconfirm>:null}]}/></Disclosure></Space>
}
export default function NasGroups({request,nas}:{request:Request;nas:Nas[]}){
 const d=useData<Group[]>(request,'nas/groups');const a=useAction(d.refresh);const [form]=Form.useForm();
 return <Space direction="vertical" className="full"><Card title="Группы NAS"><Fault error={d.error}/><Form form={form} layout="inline" onFinish={v=>a.run(()=>request('nas/groups','POST',v),()=>form.resetFields())}><Form.Item name="name" label="Группа" rules={[{required:true,max:64,pattern:/^[A-Za-z0-9_.-]+$/}]}><Input placeholder="CORE"/></Form.Item><Form.Item name="description" label="Описание"><Input maxLength={200}/></Form.Item><Button type="primary" htmlType="submit" loading={a.busy}>Создать</Button></Form><GroupList items={d.data??[]} loading={d.loading} render={group=><Details key={group.id} request={request} group={group} nas={nas}/>}/></Card></Space>
}
