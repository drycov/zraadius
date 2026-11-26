import {useState} from 'react';
import {Alert,Button,Form,Select,Space,Popconfirm} from '../ui';
import Disclosure from '../ui/Disclosure';
import {useData,useAction,Fault} from '../hooks';
import type {Request,Nas} from '../api';
type Named={id:number;name:string};
type Template={nas_id:number;profile_id:number;address_space_id:number|null};
function Editor({request,id,initial,nas,profiles,spaces,refresh}:{request:Request;id:number;initial:Template|null;nas:Nas[];profiles:Named[];spaces:Named[];refresh:()=>void}){
 const [form]=Form.useForm();const a=useAction(refresh);
 return <Space direction="vertical" className="full"><Form form={form} layout="vertical" initialValues={initial??{}} onFinish={v=>a.run(()=>request('identities/groups/'+id+'/vpn-template','PUT',{nas_id:v.nas_id,profile_id:v.profile_id,address_space_id:v.address_space_id||null}))}><Form.Item name="nas_id" label="VPN NAS" rules={[{required:true}]}><Select options={nas.filter(n=>n.type==='mikrotik'&&n.services?.includes('l2tp')).map(n=>({value:n.id,label:n.shortname}))}/></Form.Item><Form.Item name="profile_id" label="PPP Profile с пулом" rules={[{required:true}]}><Select options={profiles.map(p=>({value:p.id,label:p.name}))}/></Form.Item><Form.Item name="address_space_id" label="Address Space"><Select allowClear options={spaces.map(p=>({value:p.id,label:p.name}))}/></Form.Item><Button type="primary" htmlType="submit" loading={a.busy}>Сохранить шаблон VPN</Button></Form>{initial&&<Popconfirm title="Удалить шаблон? Уже созданные назначения сохранятся." onConfirm={()=>a.run(()=>request('identities/groups/'+id+'/vpn-template','DELETE'))}><Button danger>Удалить шаблон</Button></Popconfirm>}</Space>
}
export function GroupVpnTemplate({request,id}:{request:Request;id:number}){
 const d=useData<Template|null>(request,'identities/groups/'+id+'/vpn-template');const n=useData<Nas[]>(request,'nas');const p=useData<Named[]>(request,'ppp/profiles');const s=useData<Named[]>(request,'ppp/address-spaces');
 return <Disclosure title="Групповой шаблон VPN"><Fault error={d.error||n.error||p.error||s.error}/>{d.data!==undefined&&n.data&&p.data&&s.data&&<Editor request={request} id={id} initial={d.data} nas={n.data} profiles={p.data} spaces={s.data} refresh={d.refresh}/>}</Disclosure>
}
export function ApplyVpnTemplate({request,id,refresh}:{request:Request;id:number;refresh:()=>void}){
 const [preview,setPreview]=useState<Template>();const [error,setError]=useState('');const [busy,setBusy]=useState(false);const a=useAction(refresh);
 return <Disclosure title="Назначить VPN по глобальной группе"><Space direction="vertical" className="full"><Alert type="info" message="Создаётся отключённое индивидуальное назначение с динамическим пулом. Изменения группы не меняют ранее созданные назначения. Затем включите сервис отдельно."/><Fault error={error}/><Button loading={busy} onClick={async()=>{setBusy(true);setError('');setPreview(undefined);try{setPreview(await request<Template>('identities/'+id+'/vpn-template'))}catch(e){setError(e instanceof Error?e.message:'Ошибка')}finally{setBusy(false)}}}>Проверить шаблон</Button>{preview&&<><span>NAS #{preview.nas_id} · Profile #{preview.profile_id} · Address Space {preview.address_space_id??'legacy'}</span><Popconfirm title="Создать отключённое VPN-назначение?" onConfirm={()=>a.run(()=>request('identities/'+id+'/vpn-template/apply','POST'))}><Button type="primary" loading={a.busy}>Применить шаблон</Button></Popconfirm></>}</Space></Disclosure>
}
