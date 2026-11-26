import React,{lazy,Suspense,useCallback,useEffect,useMemo,useState} from 'react';
import {createRoot} from 'react-dom/client';
import {Alert,App,Button,Card,Checkbox,Col,Form,Input,InputNumber,Layout,Menu,Modal,Popconfirm,Row,Select,Space,Table,Tag,Typography} from './ui';
import {DashboardOutlined,UserOutlined,TeamOutlined,ClusterOutlined,HistoryOutlined,BookOutlined,LogoutOutlined,ReloadOutlined} from './ui/icons';
import {client,ApiError,type Request,type User,type Group,type Nas,type Session,type Audit,type Dashboard,type Attribute} from './api';
import './vendor/design-kit/css/index.css';
import './style.css';
import {detectScheme} from './vendor/design-kit/theme';
import {StatCard} from './vendor/design-kit/components/StatCard';
import {Alert as KitAlert} from './vendor/design-kit/components/Alert';
import {Fault} from './hooks';
import {useRoute} from './routing';
const Overview=lazy(()=>import('./pages/Overview'));
const Users=lazy(()=>import('./pages/Users'));
const Groups=lazy(()=>import('./pages/Groups'));
const NasPage=lazy(()=>import('./pages/NasPage'));
const Accounting=lazy(()=>import('./pages/Accounting'));
const Audits=lazy(()=>import('./pages/Audits'));
const Dictionary=lazy(()=>import('./pages/Dictionary'));
const ServicesPage=lazy(()=>import('./pages/ServicesPage'));
const PolicyPage=lazy(()=>import('./pages/PolicyPage'));
const IpoePage=lazy(()=>import('./pages/IpoePage'));
const IpamPage=lazy(()=>import('./pages/IpamPage'));
const HotspotPage=lazy(()=>import('./pages/HotspotPage'));
const DevicePage=lazy(()=>import('./pages/DevicePage'));
const PkiPage=lazy(()=>import('./pages/PkiPage'));
const ProxyPage=lazy(()=>import('./pages/ProxyPage'));
const IamPage=lazy(()=>import('./pages/IamPage'));
const AccountPage=lazy(()=>import('./pages/AccountPage'));

const {Header,Sider,Content}=Layout;
const {Text}=Typography;
const nav=[{key:'iam',label:'Администраторы / IAM',icon:<TeamOutlined/>},{key:'account',label:'Моя учётная запись',icon:<UserOutlined/>},{key:'proxy',label:'RADIUS Proxy',icon:<ClusterOutlined/>},{key:'pki',label:'PKI / Certificates',icon:<BookOutlined/>},{key:'device',label:'Device AAA',icon:<UserOutlined/>},{key:'hotspot',label:'Hotspot / Vouchers',icon:<ClusterOutlined/>},{key:'ipam',label:'IPAM / IP Pools',icon:<ClusterOutlined/>},{key:'ipoe',label:'IPoE / MAC',icon:<ClusterOutlined/>},{key:'policies',label:'Политики AAA',icon:<ClusterOutlined/>},{key:'services',label:'Сервисы AAA',icon:<ClusterOutlined/>},{key:'overview',label:'Dashboard',icon:<DashboardOutlined/>},{key:'users',label:'Пользователи',icon:<UserOutlined/>},{key:'groups',label:'Группы и профили',icon:<TeamOutlined/>},{key:'nas',label:'NAS',icon:<ClusterOutlined/>},{key:'accounting',label:'Accounting',icon:<HistoryOutlined/>},{key:'dictionary',label:'Словари',icon:<BookOutlined/>},{key:'audit',label:'Аудит',icon:<HistoryOutlined/>}];
function Console(){const [mfaRequired,setMfaRequired]=useState(false);const [token,setToken]=useState('');const [identity,setIdentity]=useState<{username:string;role:string}>();const [page,setPage]=useRoute();const [error,setError]=useState('');const [busy,setBusy]=useState(false);const expire=useCallback(()=>{setToken('');setIdentity(undefined);setMfaRequired(false);setError('Сессия завершена. Войдите повторно.')},[]);const request=useMemo(()=>client(token,expire),[token,expire]);const views:Record<string,React.ComponentType<{request:Request}>>={iam:IamPage,account:AccountPage,proxy:ProxyPage,pki:PkiPage,device:DevicePage,hotspot:HotspotPage,ipam:IpamPage,ipoe:IpoePage,policies:PolicyPage,services:ServicesPage,overview:Overview,users:Users,groups:Groups,nas:NasPage,accounting:Accounting,dictionary:Dictionary,audit:Audits};const effectivePage=page==='iam'&&identity?.role!=='admin'?'overview':page;const View=views[effectivePage]??Overview;
 if(!token)return <main className="login"><Card title="ZRADIUS / Management Console"><Text type="secondary">Вход в систему управления</Text><Fault error={error}/><Form layout="vertical" onFinish={async v=>{setBusy(true);setError('');try{const result=await client('')<{access_token?:string;username:string;role:string;mfa_required?:boolean}>('iam/login','POST',v);if(result.mfa_required){setMfaRequired(true);return}if(!result.access_token)throw new Error('Missing session');setMfaRequired(false);setIdentity(result);setToken(result.access_token)}catch(e){setError(e instanceof ApiError&&e.status===401?'Неверные учётные данные или код MFA':e instanceof ApiError&&e.status===429?'Слишком много попыток входа':'API недоступен')}finally{setBusy(false)}}}><Form.Item name="username" label="Логин" rules={[{required:true}]}><Input autoComplete="username"/></Form.Item><Form.Item name="password" label="Пароль" rules={[{required:true}]}><Input.Password autoComplete="current-password"/></Form.Item>{mfaRequired&&<Form.Item name="otp" label="Код TOTP или резервный код" rules={[{required:true}]}><Input autoComplete="one-time-code"/></Form.Item>}<Button block type="primary" htmlType="submit" loading={busy}>Войти</Button></Form></Card></main>;
 return <Layout className="shell"><Sider breakpoint="lg" collapsedWidth="0" width={260}><div className="brand dk-sidebar__brand">ZRADIUS <small>AAA Management</small></div><Menu mode="inline" items={nav.filter(n=>n.key!=='iam'||identity?.role==='admin')} selectedKeys={[effectivePage]} onClick={e=>setPage(e.key)}/></Sider><Layout><Header className="header"><Text>{identity?.username} <Tag>{identity?.role}</Tag></Text><Button icon={<LogoutOutlined/>} onClick={async()=>{try{await request('iam/logout','POST')}finally{setToken('');setIdentity(undefined);setPage('overview')}}}>Выход</Button></Header><Content className="content dk-content"><div className="dk-page-head"><h1>{nav.find(n=>n.key===effectivePage)?.label}</h1></div><Suspense fallback={<div role="status">Загрузка раздела…</div>}><View key={effectivePage} request={request}/></Suspense></Content></Layout></Layout>
}
function Root(){
 const [scheme,setScheme]=useState(detectScheme);
 useEffect(()=>{const media=window.matchMedia('(prefers-color-scheme: light)');const update=()=>setScheme(detectScheme());media.addEventListener('change',update);return()=>media.removeEventListener('change',update)},[]);
 useEffect(()=>{document.documentElement.setAttribute('data-tg-theme',scheme);document.body.classList.add('dk-body')},[scheme]);
 return <App><Console/></App>
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><Root/></React.StrictMode>);
