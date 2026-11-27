import {useEffect,useState} from 'react';
import Tabs from '../ui/Tabs';
import IdentityDirectory from './IdentityDirectory';
import IdentityAudit from './IdentityAudit';
import IdentityLegacy from './IdentityLegacy';
import IdentityBulkState from './IdentityBulkState';
import IdentityBulk from './IdentityBulk';
import BulkAccessProfiles from './BulkAccessProfiles';
import IdentitySessions from './IdentitySessions';
import {EapFields} from './IdentityEap';
import {HotspotFields} from './IdentityHotspot';
import {PppoeFields} from './IdentityPppoe';
import {ApplyVpnTemplate} from './IdentityVpnTemplate';
import IdentityPolicies from './IdentityPolicies';
import IdentityAaaPolicy from './IdentityAaaPolicy';
import IdentityPolicySimulator from './IdentityPolicySimulator';
import CentralizedPolicyRules from './CentralizedPolicyRules';
import IdentityAccessProfile from './IdentityAccessProfile';
import IdentityReconciliation from './IdentityReconciliation';
import IdentityPolicyHistory from './IdentityPolicyHistory';
import PolicyCompliance from './PolicyCompliance';
import AccessTemplates,{type AccessTemplate} from './AccessTemplates';
import ServiceAccountRegistry,{IdentityLifecycle} from './ServiceAccountRegistry';
import IdentityGroups,{IdentityMembership} from './IdentityGroups';
import {Alert,Button,Checkbox,Form,Input,Select,Space,Table,Tag,Modal,Popconfirm} from '../ui';
import {useData,useAction,Fault} from '../hooks';
import type {Request,Nas} from '../api';
type Identity={access_template_id:number|null;account_type:"person"|"service";account_owner:string;account_purpose:string;console_id:number|null;console_role:string|null;console_enabled:boolean|null;dot1x_assigned:boolean;dot1x_enabled:boolean|null;wpa_assigned:boolean;wpa_enabled:boolean|null;hotspot_assigned:boolean;hotspot_enabled:boolean|null;pppoe_assigned:boolean;pppoe_enabled:boolean|null;credentials_ready:boolean;mschap_ready:boolean;id:number;username:string;full_name:string;department:string;enabled:boolean;device_id:number|null;device_enabled:boolean|null;l2tp_id:number|null;l2tp_enabled:boolean|null};
type Profile={id:number;name:string};
export default function UnifiedUsers({request}:{request:Request}){
 const [kind,setKind]=useState('all');const [createKind,setCreateKind]=useState('person');const [offset,setOffset]=useState(0);const [query,setQuery]=useState('');const [search,setSearch]=useState('');const [status,setStatus]=useState('all');const d=useData<Identity[]>(request,'identities?limit=101&offset='+offset+'&q='+encodeURIComponent(search)+(status==='all'?'':'&enabled='+status)+(kind==='all'?'':'&account_type='+kind));const n=useData<Nas[]>(request,'nas');const p=useData<Profile[]>(request,'ppp/profiles');const r=useData<{name:string}[]>(request,'device-aaa/roles');
 const a=useAction(d.refresh);const [form]=Form.useForm();const [consoleAccess,setConsoleAccess]=useState(false);const [dot1x,setDot1x]=useState(false);const [wpa,setWpa]=useState(false);const [hotspot,setHotspot]=useState(false);const [pppoe,setPppoe]=useState(false);const [device,setDevice]=useState(false);const [vpn,setVpn]=useState(false);const [editing,setEditing]=useState<Identity>();
 const [active,setActive]=useState(()=>sessionStorage.getItem('zr-create-service')?'create':'catalog');
 const [initialService]=useState(()=>sessionStorage.getItem('zr-create-service')??'');
 useEffect(()=>{sessionStorage.removeItem('zr-create-service');if(initialService==='device-aaa')setDevice(true);if(initialService==='l2tp')setVpn(true);if(initialService==='console')setConsoleAccess(true);if(initialService==='pppoe')setPppoe(true);},[initialService]);
 const templates=useData<AccessTemplate[]>(request,'identities/access-templates');
 const [templateId,setTemplateId]=useState('manual');
 const applyTemplate=(value:string)=>{setTemplateId(value);const t=templates.data?.find(x=>String(x.id)===value&&x.enabled&&x.account_type===createKind);if(!t)return;const p=t.parameters??{};form.setFieldsValue({device_nas:p.device?.nas_id,device_role:p.device?.role,filter_id:p.device?.filter_id,vpn_nas:p.l2tp?.nas_id,vpn_profile:p.l2tp?.profile_id,pppoe_nas:p.pppoe?.nas_id,pppoe_rate:p.pppoe?.rate_limit,pppoe_pool:p.pppoe?.pool,pppoe_interim:p.pppoe?.interim_seconds,hotspot_nas:p.hotspot?.nas_id,hotspot_rate:p.hotspot?.rate_limit,hotspot_session:p.hotspot?.session_seconds,hotspot_idle:p.hotspot?.idle_seconds,dot1x_nas:p.dot1x?.nas_id,dot1x_vlan:p.dot1x?.vlan_id,'wpa-enterprise_nas':p.wpa_enterprise?.nas_id,'wpa-enterprise_vlan':p.wpa_enterprise?.vlan_id,console_role:p.console_role,static_ip:undefined});const s=t.services;setDevice(s.includes('device-aaa'));setVpn(s.includes('l2tp'));setPppoe(s.includes('pppoe'));setHotspot(s.includes('hotspot'));setDot1x(s.includes('dot1x'));setWpa(s.includes('wpa-enterprise'));setConsoleAccess(createKind==='person'&&s.includes('console'));};
 const nas=(service:string)=>(n.data??[]).filter(x=>x.type==='mikrotik'&&x.services?.includes(service)).map(x=>({value:x.id,label:x.shortname}));
 return <Space direction="vertical" className="full"><Fault error={d.error||n.error||p.error||r.error}/><Tabs label="Единый каталог" active={active} onChange={setActive} items={[
 {id:'catalog',label:'Каталог',content:<><div className="zr-workspace-toolbar"><Input.Search aria-label="Поиск пользователей" placeholder="Логин, ФИО, подразделение" value={query} maxLength={200} onChange={e=>setQuery(e.target.value)}/><Button onClick={()=>{setOffset(0);setSearch(query.trim())}}>Найти</Button><Button onClick={()=>{setOffset(0);setQuery('');setSearch('');setStatus('all');setKind('all')}}>Сбросить</Button><Select value={status} onChange={v=>{setOffset(0);setStatus(String(v))}} options={[{value:'all',label:'Все статусы'},{value:'true',label:'Активные'},{value:'false',label:'Заблокированные'}]}/><Select value={kind} onChange={v=>{setOffset(0);setKind(String(v))}} options={[{value:"all",label:"Все типы"},{value:"person",label:"Пользователи"},{value:"service",label:"Сервисные УЗ"}]}/><Button type="primary" onClick={()=>setActive('create')}>Создать учётную запись</Button><Button onClick={d.refresh}>Обновить</Button></div><Table<Identity> rowKey="id" loading={d.loading} dataSource={(d.data??[]).slice(0,100)} pagination={false} scroll={{x:760}} columns={[{title:'Логин',dataIndex:'username'},{title:'Тип',render:(_,x)=><Tag color={x.account_type==='service'?'orange':'blue'}>{x.account_type==='service'?'Сервисная УЗ':'Пользователь'}</Tag>},{title:'Имя / назначение',render:(_,x)=>x.account_type==='service'?x.account_purpose:x.full_name},{title:'Подразделение',dataIndex:'department'},{title:'Профиль доступа',render:(_,x)=>x.access_template_id===null?'—':(templates.data??[]).find(t=>t.id===x.access_template_id)?.name??('#'+x.access_template_id)},{title:'Статус',render:(_,x)=><Tag color={x.enabled?'green':'red'}>{x.enabled?'Активен':'Заблокирован'}</Tag>},{title:'Сервисы',render:(_,x)=><div className="zr-service-tags">{[[x.device_enabled,'AAA'],[x.l2tp_enabled,'L2TP'],[x.pppoe_enabled,'PPPoE'],[x.hotspot_enabled,'Hotspot'],[x.dot1x_enabled,'802.1X'],[x.wpa_enabled,'WPA'],[x.console_enabled,'Console']].filter(([enabled])=>enabled).map(([,label])=><Tag key={String(label)} color={x.enabled?'green':'orange'}>{label}</Tag>)}</div>},{title:'Действия',render:(_,x)=><Space wrap><Button onClick={()=>{setEditing(x)}}>Настроить</Button><Popconfirm title={x.enabled?'Заблокировать все сервисы пользователя? Активные сетевые сессии могут сохраниться.':'Включить пользователя?'} onConfirm={()=>a.run(()=>request('identities/'+x.id+'/state','PUT',{enabled:!x.enabled}))}><Button disabled={a.busy} danger={x.enabled}>{x.enabled?'Блокировать все':'Включить'}</Button></Popconfirm></Space>}]}/><Space wrap><Button disabled={!offset||d.loading} onClick={()=>setOffset(v=>Math.max(0,v-100))}>Назад</Button><span>Страница {offset/100+1}</span><Button disabled={d.loading||(d.data?.length??0)<=100} onClick={()=>setOffset(v=>v+100)}>Далее</Button></Space></>},
 {id:'create',label:'Создание',content:<><Alert type="info" message="Один логин и пароль. Выберите необходимые сервисы."/> <Form form={form} layout="vertical" disabled={a.busy} onFinish={v=>a.run(()=>request('identities','POST',{username:v.username,access_template_id:templateId==='manual'?null:Number(templateId),account_type:createKind,account_owner:createKind==='service'?v.account_owner:'',account_purpose:createKind==='service'?v.account_purpose:'',full_name:v.full_name??'',department:v.department??'',password:v.password,console_role:createKind==='person'&&consoleAccess?v.console_role:null,dot1x:dot1x?{nas_id:v.dot1x_nas,vlan_id:v.dot1x_vlan||null}:null,wpa_enterprise:wpa?{nas_id:v['wpa-enterprise_nas'],vlan_id:v['wpa-enterprise_vlan']||null}:null,hotspot:hotspot?{nas_id:v.hotspot_nas,rate_limit:v.hotspot_rate,session_seconds:v.hotspot_session??3600,idle_seconds:v.hotspot_idle??300}:null,pppoe:pppoe?{nas_id:v.pppoe_nas,rate_limit:v.pppoe_rate,pool:v.pppoe_pool,interim_seconds:v.pppoe_interim??300}:null,device:device?{nas_id:v.device_nas,role:v.device_role,filter_id:v.filter_id||null}:null,l2tp:vpn?{nas_id:v.vpn_nas,profile_id:v.vpn_profile,static_ip:v.static_ip||null}:null}),()=>{form.resetFields();setTemplateId('manual');setCreateKind('person');setDevice(false);setVpn(false);setPppoe(false);setHotspot(false);setDot1x(false);setWpa(false);setConsoleAccess(false);setActive('catalog')})}>
 <label>Тип учётной записи</label><Select value={createKind} onChange={v=>{setCreateKind(String(v));setTemplateId('manual');setConsoleAccess(false);setDevice(false);setVpn(false);setPppoe(false);setHotspot(false);setDot1x(false);setWpa(false)}} options={[{value:"person",label:"Персональная учётная запись"},{value:"service",label:"Сервисная учётная запись"}]}/><label>Шаблон доступа</label><Fault error={templates.error}/><Select value={templateId} onChange={v=>applyTemplate(String(v))} options={[{value:"manual",label:"Ручная настройка"},...(templates.data??[]).filter(t=>t.enabled&&t.account_type===createKind).map(t=>({value:String(t.id),label:t.name}))]}/><Alert type="info" message="Шаблон сохраняется как профиль доступа и заполняет услуги. Проверьте NAS, роли и настройки перед созданием. Индивидуальные изменения будут отражены в сравнении профиля."/>{createKind==="service"&&<><Alert type="info" message="Сервисная УЗ предназначена для технических подключений. Доступ к Web Console запрещён."/><Form.Item name="account_owner" label="Ответственный" rules={[{required:true,max:200}]}><Input/></Form.Item><Form.Item name="account_purpose" label="Назначение" rules={[{required:true,max:500}]}><Input/></Form.Item></>}<Form.Item name="username" label="Логин" rules={[{required:true,max:64}]}><Input/></Form.Item><Form.Item name="full_name" label="ФИО"><Input maxLength={200}/></Form.Item><Form.Item name="department" label="Подразделение"><Input maxLength={200}/></Form.Item><Form.Item name="password" label="Единый пароль" rules={[{required:true,min:16,max:128}]}><Input.Password autoComplete="new-password"/></Form.Item>
 <Checkbox checked={device} onChange={e=>setDevice(e.target.checked)}>Device AAA</Checkbox>
 {device&&<><Form.Item name="device_nas" label="Device NAS" rules={[{required:true}]}><Select options={nas('device-aaa')}/></Form.Item><Form.Item name="device_role" label="RouterOS Role" rules={[{required:true}]}><Select options={(r.data??[]).map(x=>({value:x.name,label:x.name}))}/></Form.Item><Form.Item name="filter_id" label="Filter-Id"><Input/></Form.Item></>}
 <Checkbox checked={vpn} onChange={e=>setVpn(e.target.checked)}>L2TP VPN</Checkbox>
 {vpn&&<><Form.Item name="vpn_nas" label="VPN NAS" rules={[{required:true}]}><Select options={nas('l2tp')}/></Form.Item><Form.Item name="vpn_profile" label="PPP Profile" rules={[{required:true}]}><Select options={(p.data??[]).map(x=>({value:x.id,label:x.name}))}/></Form.Item><Form.Item name="static_ip" label="Static IPv4"><Input/></Form.Item></>}
 <Checkbox checked={pppoe} onChange={e=>setPppoe(e.target.checked)}>PPPoE</Checkbox>{pppoe&&<PppoeFields nas={n.data??[]}/>}<Checkbox checked={hotspot} onChange={e=>setHotspot(e.target.checked)}>Hotspot</Checkbox>{hotspot&&<HotspotFields nas={n.data??[]}/>}<Checkbox checked={dot1x} onChange={e=>setDot1x(e.target.checked)}>802.1X</Checkbox>{dot1x&&<EapFields nas={n.data??[]} service="dot1x"/>}<Checkbox checked={wpa} onChange={e=>setWpa(e.target.checked)}>WPA Enterprise</Checkbox>{wpa&&<EapFields nas={n.data??[]} service="wpa-enterprise"/>}<Checkbox disabled={createKind==="service"} checked={consoleAccess} onChange={e=>setConsoleAccess(e.target.checked)}>Web Console</Checkbox>{consoleAccess&&<Form.Item name="console_role" label="Роль Web Console" rules={[{required:true}]}><Select options={[{value:"auditor",label:"Auditor"},{value:"operator",label:"Operator"},{value:"admin",label:"Administrator"}]}/></Form.Item>}<Button type="primary" htmlType="submit" loading={a.busy}>Создать единого пользователя</Button></Form></>},
 {id:'service-registry',label:'Сервисные УЗ',content:<ServiceAccountRegistry request={request} refresh={d.refresh}/>},
 {id:'templates',label:'Шаблоны доступа',content:<AccessTemplates request={request} refresh={templates.refresh}/>},
 {id:'bulk',label:'Массовое назначение',content:<IdentityBulk request={request} refresh={d.refresh}/>},
 {id:'bulk-profiles',label:'Массовые профили',content:<BulkAccessProfiles request={request} refresh={d.refresh}/>},
 {id:'policy-compliance',label:'Соответствие политикам',content:<PolicyCompliance request={request}/>},
 {id:'bulk-state',label:'Массовая блокировка',content:<IdentityBulkState request={request} refresh={d.refresh}/>},
 {id:'legacy',label:'Миграция Legacy',content:<IdentityLegacy request={request} refresh={d.refresh}/>},
 {id:'directory',label:'Active Directory',content:<IdentityDirectory request={request}/>},
 {id:'groups',label:'Глобальные группы',content:<IdentityGroups request={request}/>}
 ]}/><Modal wide title={editing?.username} open={!!editing} onCancel={()=>setEditing(undefined)} footer={null}>{editing&&<Tabs key={editing.id} label="Настройки пользователя" items={[
 ...(editing.account_type==='service'?[{id:'lifecycle',label:'Жизненный цикл',content:<IdentityLifecycle key={editing.id} request={request} id={editing.id} refresh={d.refresh}/>}]:[]),
 {id:'general',label:'Профиль и сервисы',content:<IdentityWorkspace key={editing.id} request={request} identity={editing} nas={n.data??[]} profiles={p.data??[]} roles={r.data??[]} onSaved={()=>{setEditing(undefined);d.refresh()}}/>},
 {id:'access-profile',label:'Профиль доступа',content:<IdentityAccessProfile key={editing.id+'-'+editing.account_type} request={request} id={editing.id} kind={editing.account_type} onSaved={id=>{setEditing(current=>current?{...current,access_template_id:id}:current);d.refresh()}}/>},
 {id:'reconciliation',label:'Согласование профиля',content:<IdentityReconciliation key={editing.id} request={request} id={editing.id}/>},
 {id:'policy-history',label:'История политик',content:<IdentityPolicyHistory key={editing.id} request={request} id={editing.id}/>},
 {id:'aaa-policy',label:'AAA Policy Engine',content:<IdentityAaaPolicy key={editing.id} request={request} id={editing.id}/>},
 {id:'centralized-policy',label:'Правила доступа',content:<CentralizedPolicyRules key={editing.id} request={request} id={editing.id}/>},
 {id:'policy-simulator',label:'Симулятор AAA',content:<IdentityPolicySimulator key={editing.id} request={request} id={editing.id}/>},
 {id:'policies',label:'AAA / VPN',content:<><IdentityPolicies request={request} id={editing.id} device={!!editing.device_id} vpn={!!editing.l2tp_id}/>{!editing.l2tp_id&&<ApplyVpnTemplate request={request} id={editing.id} refresh={()=>{setEditing(undefined);d.refresh()}}/>}</>},
 {id:'groups',label:'Группы',content:<IdentityMembership request={request} id={editing.id}/>},
 {id:'sessions',label:'Сессии',content:<IdentitySessions request={request} id={editing.id}/>},
 {id:'audit',label:'Аудит',content:<IdentityAudit key={editing.id} request={request} id={editing.id}/>}
 ]}/>}</Modal></Space>
}
function IdentityWorkspace({request,identity,nas,profiles,roles,onSaved}:{request:Request;identity:Identity;nas:Nas[];profiles:Profile[];roles:{name:string}[];onSaved:()=>void}){
 const [form]=Form.useForm();const a=useAction(()=>{});
 type Vpn={nas_id:number;profile_id:number|null;group_id:number|null;address_space_id:number|null;static_ip:string|null;description:string};
 type Rate={nas_id:number;rate_limit:string;pool?:string;interim_seconds?:number;session_seconds?:number;idle_seconds?:number};
 type Eap={nas_id:number;vlan_id:number|null};
 const path='identities/'+identity.id;
 type Grant={nas_id:number;role:string|null;filter_id:string|null;profile_id:number|null};
 const assignments=useData<{l2tp:Vpn|null;device_grants:Grant[];device_groups:Profile[]}>(request,path+'/assignments');
 const pp=useData<Rate|null>(request,path+'/pppoe');
 const hs=useData<Rate|null>(request,path+'/hotspot');
 const dx=useData<Eap|null>(request,path+'/eap/dot1x');
 const wp=useData<Eap|null>(request,path+'/eap/wpa-enterprise');
 const vpnGroups=useData<Profile[]>(request,'ppp/groups');
 const spaces=useData<Profile[]>(request,'ppp/address-spaces');
 const replyProfiles=useData<Profile[]>(request,'device-aaa/reply-profiles');
 const deviceGroups=useData<Profile[]>(request,'device-aaa/groups');
 const [grants,setGrants]=useState<Grant[]|null>(null);
 const [members,setMembers]=useState<number[]>([]);
 const [grantNas,setGrantNas]=useState<number|undefined>();
 const [grantRole,setGrantRole]=useState('read');
 const [grantFilter,setGrantFilter]=useState('');
 const [grantProfile,setGrantProfile]=useState('manual');
 const [editParams,setEditParams]=useState<Record<string,boolean>>({});
 const ready=[assignments,pp,hs,dx,wp,vpnGroups,spaces].every(x=>!x.loading&&!x.error&&x.data!==undefined);
 const beginEdit=(key:string)=>{
  const v=assignments.data?.l2tp,p=pp.data,h=hs.data,d=dx.data,w=wp.data;
  if(key==='l2tp'&&v)form.setFieldsValue({vpn_nas:v.nas_id,vpn_profile:v.profile_id??undefined,vpn_group:v.group_id??undefined,address_space_id:v.address_space_id??undefined,static_ip:v.static_ip??'',vpn_description:v.description});
  if(key==='pppoe'&&p)form.setFieldsValue({pppoe_nas:p.nas_id,pppoe_rate:p.rate_limit,pppoe_pool:p.pool,pppoe_interim:p.interim_seconds});
  if(key==='hotspot'&&h)form.setFieldsValue({hotspot_nas:h.nas_id,hotspot_rate:h.rate_limit,hotspot_session:h.session_seconds,hotspot_idle:h.idle_seconds});
  if(key==='dot1x'&&d)form.setFieldsValue({dot1x_nas:d.nas_id,dot1x_vlan:d.vlan_id});
  if(key==='wpa_enterprise'&&w)form.setFieldsValue({'wpa-enterprise_nas':w.nas_id,'wpa-enterprise_vlan':w.vlan_id});
  setEditParams(old=>({...old,[key]:true}));
 };
 const initial={device:!!identity.device_enabled,l2tp:!!identity.l2tp_enabled,pppoe:!!identity.pppoe_enabled,hotspot:!!identity.hotspot_enabled,dot1x:!!identity.dot1x_enabled,wpa_enterprise:!!identity.wpa_enabled,console:!!identity.console_enabled};
 type Service=keyof typeof initial;
 const [enabled,setEnabled]=useState(initial);
 const assigned:Record<Service,boolean>={device:!!identity.device_id,l2tp:!!identity.l2tp_id,pppoe:identity.pppoe_assigned,hotspot:identity.hotspot_assigned,dot1x:identity.dot1x_assigned,wpa_enterprise:identity.wpa_assigned,console:!!identity.console_id};
 const [role,setRole]=useState(identity.console_role??'auditor');
 const [kind,setKind]=useState(identity.account_type);
 const [fullName,setFullName]=useState(identity.full_name);
 const [department,setDepartment]=useState(identity.department);
 const [owner,setOwner]=useState(identity.account_owner);
 const [purpose,setPurpose]=useState(identity.account_purpose);
 const groupList=useData<{id:number;name:string}[]>(request,'identities/groups');
 const membership=useData<{group_ids:number[]}>(request,'identities/'+identity.id+'/groups');
 const [groupIds,setGroupIds]=useState<number[]|null>(null);
 const templateList=useData<AccessTemplate[]>(request,'identities/access-templates');
 const [template,setTemplate]=useState(String(identity.access_template_id??'none'));
 const eligible=(service:string)=>nas.filter(x=>x.type==='mikrotik'&&x.services?.includes(service)).map(x=>({value:x.id,label:x.shortname}));
 const toggle=(key:Service,label:string)=><Checkbox checked={enabled[key]} disabled={a.busy||(key==='console'&&kind==='service')} onChange={e=>setEnabled(v=>({...v,[key]:e.target.checked}))}>{label}{assigned[key]?' — назначен':''}</Checkbox>;
 const changed=(key:Service)=>enabled[key]!==initial[key]||(enabled[key]&&!!editParams[key]);
 const editingParams=(key:Service)=>enabled[key]&&(!assigned[key]||!!editParams[key]);
 const editButton=(key:Service)=>(enabled[key]&&assigned[key]&&!editParams[key])?<Button disabled={!ready||a.busy} onClick={()=>beginEdit(key)}>Изменить параметры</Button>:null;
 return <Space direction="vertical" className="full">
 <Alert type="info" message="Все изменения сохраняются одной транзакцией. Отключение сохраняет параметры назначения; активные сетевые сессии могут продолжаться."/>
 {!identity.credentials_ready&&<Alert type="warning" message="Для включения сервисов установите единый пароль."/>}
 <Form form={form} layout="vertical" disabled={a.busy} onFinish={v=>a.run(()=>{
 const payload:Record<string,unknown>={};
 if(fullName.trim()!==identity.full_name||department.trim()!==identity.department)payload.metadata={full_name:fullName,department};
 if(kind!==identity.account_type||owner.trim()!==identity.account_owner||purpose.trim()!==identity.account_purpose)payload.profile={account_type:kind,account_owner:owner,account_purpose:purpose};
 if(groupIds!==null)payload.groups={group_ids:groupIds};
 if(template!==String(identity.access_template_id??'none'))payload.access_profile={template_id:template==='none'?null:Number(template),preview:false};
 if(v.password)payload.password={password:v.password};
 if(changed('device')||changed('l2tp'))payload.services={device:enabled.device,l2tp:enabled.l2tp,device_assignment:enabled.device&&!assigned.device?{nas_id:v.device_nas,role:v.device_role,filter_id:v.filter_id||null}:null,l2tp_assignment:editingParams('l2tp')?{nas_id:v.vpn_nas,profile_id:v.vpn_profile||null,group_id:v.vpn_group||null,address_space_id:v.address_space_id||null,static_ip:v.static_ip||null,description:v.vpn_description??''}:null};
 if(grants!==null&&assigned.device)payload.device_policy={grants:grants.map(g=>g.profile_id?{nas_id:g.nas_id,profile_id:g.profile_id}:{nas_id:g.nas_id,role:g.role,filter_id:g.filter_id}),group_ids:members};
 if(changed('pppoe'))payload.pppoe={enabled:enabled.pppoe,assignment:editingParams('pppoe')?{nas_id:v.pppoe_nas,rate_limit:v.pppoe_rate,pool:v.pppoe_pool,interim_seconds:v.pppoe_interim??300}:null};
 if(changed('hotspot'))payload.hotspot={enabled:enabled.hotspot,assignment:editingParams('hotspot')?{nas_id:v.hotspot_nas,rate_limit:v.hotspot_rate,session_seconds:v.hotspot_session??3600,idle_seconds:v.hotspot_idle??300}:null};
 for(const key of ['dot1x','wpa_enterprise'] as const){const field=key==='dot1x'?'dot1x':'wpa-enterprise';if(changed(key))payload[key]={enabled:enabled[key],assignment:editingParams(key)?{nas_id:v[field+'_nas'],vlan_id:v[field+'_vlan']||null}:null};}
 if(kind==='person'&&(changed('console')||(enabled.console&&role!==identity.console_role)))payload.console={enabled:enabled.console,role};
 if(!Object.keys(payload).length)return Promise.resolve();
 return request('identities/'+identity.id+'/workspace','PUT',payload);
 },onSaved)}>
 <label>Логин<Input value={identity.username} readOnly/></label>
 <label>Тип учётной записи<Select value={kind} onChange={v=>{setKind(v==='service'?'service':'person');setTemplate('none')}} options={[{value:'person',label:'Персональная'},{value:'service',label:'Сервисная'}]}/></label>
 <label>ФИО<Input value={fullName} maxLength={200} onChange={e=>setFullName(e.target.value)}/></label>
 <label>Подразделение<Input value={department} maxLength={200} onChange={e=>setDepartment(e.target.value)}/></label>
 {kind==='service'&&<><label>Ответственный<Input value={owner} maxLength={200} onChange={e=>setOwner(e.target.value)}/></label><label>Назначение<Input value={purpose} maxLength={500} onChange={e=>setPurpose(e.target.value)}/></label></>}
 <Fault error={groupList.error||membership.error||templateList.error||assignments.error||pp.error||hs.error||dx.error||wp.error||vpnGroups.error||spaces.error}/>
 <label>Глобальные группы<Select mode="multiple" disabled={!membership.data||!groupList.data||a.busy} value={groupIds??membership.data?.group_ids??[]} onChange={setGroupIds} options={(groupList.data??[]).map(x=>({value:x.id,label:x.name}))}/></label>
 <label>Профиль доступа<Select value={template} disabled={!templateList.data||a.busy} onChange={v=>setTemplate(String(v))} options={[{value:'none',label:'Без профиля'},...(templateList.data??[]).filter(t=>t.enabled&&t.account_type===kind).map(t=>({value:String(t.id),label:t.name}))]}/></label>
 <Alert type="info" message="Назначение профиля не применяет автоматически сетевые настройки. Для этого используется согласование профиля."/>
 {toggle('device','Device AAA')}{assigned.device&&<><Fault error={replyProfiles.error||deviceGroups.error}/>{grants===null?<Button disabled={a.busy||!assignments.data||!replyProfiles.data||!deviceGroups.data} onClick={()=>{setGrants(assignments.data?.device_grants??[]);setMembers(assignments.data?.device_groups.map(g=>g.id)??[])}}>Настроить разрешения NAS и группы</Button>:<Space direction="vertical" className="full">
 <Alert type="warning" message="Список прямых разрешений и групп заменяется только при общем сохранении. Удаление прямого разрешения не отменяет наследуемый доступ."/>
 <Table<Grant> rowKey="nas_id" pagination={false} dataSource={grants} columns={[{title:'NAS',render:(_,g)=>nas.find(n=>n.id===g.nas_id)?.shortname??g.nas_id},{title:'Role',dataIndex:'role'},{title:'Filter-Id',dataIndex:'filter_id'},{title:'Reply Profile',render:(_,g)=>replyProfiles.data?.find(p=>p.id===g.profile_id)?.name??'—'},{title:'Действия',render:(_,g)=><Space><Button disabled={a.busy} onClick={()=>{setGrantNas(g.nas_id);setGrantRole(g.role??'read');setGrantFilter(g.filter_id??'');setGrantProfile(String(g.profile_id??'manual'))}}>Изменить</Button><Button danger disabled={a.busy} onClick={()=>setGrants(old=>old?.filter(x=>x.nas_id!==g.nas_id)??null)}>Убрать</Button></Space>}]}/>
 <label>NAS<Select value={grantNas} onChange={v=>setGrantNas(Number(v))} options={eligible('device-aaa')}/></label>
 <label>Reply Profile<Select value={grantProfile} onChange={v=>setGrantProfile(String(v))} options={[{value:'manual',label:'Ручные атрибуты'},...(replyProfiles.data??[]).map(p=>({value:String(p.id),label:p.name}))]}/></label>
 {grantProfile==='manual'&&<><label>RouterOS Role<Select value={grantRole} onChange={v=>setGrantRole(String(v))} options={roles.map(r=>({value:r.name,label:r.name}))}/></label><label>Filter-Id<Input value={grantFilter} maxLength={64} onChange={e=>setGrantFilter(e.target.value)}/></label></>}
 <Button disabled={a.busy||!grantNas||(grantProfile==='manual'&&!roles.some(r=>r.name===grantRole))} onClick={()=>{if(!grantNas)return;const g:Grant={nas_id:grantNas,role:grantProfile==='manual'?grantRole:null,filter_id:grantProfile==='manual'?grantFilter||null:null,profile_id:grantProfile==='manual'?null:Number(grantProfile)};setGrants(old=>[...(old??[]).filter(x=>x.nas_id!==g.nas_id),g]);setGrantNas(undefined)}}>Добавить / обновить разрешение</Button>
 <label>Группы Device AAA<Select mode="multiple" value={members} onChange={setMembers} options={(deviceGroups.data??[]).map(g=>({value:g.id,label:g.name}))}/></label>
 <Button disabled={a.busy} onClick={()=>setGrants(null)}>Отменить редактирование разрешений</Button>
 </Space>}</>}
 {enabled.device&&!assigned.device&&<><Form.Item name="device_nas" label="Device NAS" rules={[{required:true}]}><Select options={eligible('device-aaa')}/></Form.Item><Form.Item name="device_role" label="RouterOS Role" rules={[{required:true}]}><Select options={roles.map(x=>({value:x.name,label:x.name}))}/></Form.Item><Form.Item name="filter_id" label="Filter-Id"><Input/></Form.Item></>}
 {toggle('l2tp','L2TP VPN')}{editButton('l2tp')}
 {editingParams('l2tp')&&<><Form.Item name="vpn_nas" label="VPN NAS" rules={[{required:true}]}><Select options={eligible('l2tp')}/></Form.Item><Form.Item name="vpn_profile" label="PPP Profile"><Select allowClear options={profiles.map(x=>({value:x.id,label:x.name}))}/></Form.Item><Form.Item name="vpn_group" label="VPN Group"><Select allowClear options={(vpnGroups.data??[]).map(x=>({value:x.id,label:x.name}))}/></Form.Item><Form.Item name="address_space_id" label="Address Space / VRF"><Select allowClear options={(spaces.data??[]).map(x=>({value:x.id,label:x.name}))}/></Form.Item><Form.Item name="static_ip" label="Static IPv4"><Input/></Form.Item><Form.Item name="vpn_description" label="Описание"><Input maxLength={200}/></Form.Item></>}
 {toggle('pppoe','PPPoE')}{editButton('pppoe')}{editingParams('pppoe')&&<PppoeFields nas={nas}/>}
 {toggle('hotspot','Hotspot')}{editButton('hotspot')}{editingParams('hotspot')&&<HotspotFields nas={nas}/>}
 {toggle('dot1x','802.1X')}{editButton('dot1x')}{editingParams('dot1x')&&<EapFields nas={nas} service="dot1x"/>}
 {toggle('wpa_enterprise','WPA Enterprise')}{editButton('wpa_enterprise')}{editingParams('wpa_enterprise')&&<EapFields nas={nas} service="wpa-enterprise"/>}
 {toggle('console','Web Console')}{enabled.console&&kind==='person'&&<Select value={role} onChange={v=>setRole(String(v))} options={['auditor','operator','admin'].map(x=>({value:x,label:x}))}/>}
 <Form.Item name="password" label="Новый единый пароль (необязательно)" rules={[{min:16,max:128}]}><Input.Password autoComplete="new-password"/></Form.Item>
 <Button type="primary" htmlType="submit" loading={a.busy} disabled={!ready||(kind==='service'&&(!owner.trim()||!purpose.trim()||enabled.console))}>Сохранить профиль и сервисы</Button>
 </Form></Space>
}
