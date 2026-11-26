import React,{useEffect,useMemo,useState} from 'react';
import {Alert,App,Button,Card,Checkbox,Col,Form,Input,InputNumber,Modal,Popconfirm,Row,Select,Space,Table,Tag,Typography} from '../ui';
import {ReloadOutlined} from '../ui/icons';
import {type Request,type User,type Group,type Nas,type Session,type Audit,type Dashboard,type Attribute} from '../api';
import {StatCard} from '../vendor/design-kit/components/StatCard';
import MfaPanel from '../MfaPanel';
import {enc,useData,useAction,Fault} from '../hooks';
const {Text}=Typography;
export default function Overview({request}:{request:Request}){
 const d=useData<Dashboard>(request,'dashboard');
 const labels:Record<keyof Dashboard,string>={users:'Пользователи',disabled_users:'Заблокированные',groups:'Группы',nas:'NAS в реестре',open_sessions:'Открытые записи сессий',accounting_records:'Записи Accounting',audit_24h:'Операции за 24 часа'};
 return <Space direction="vertical" size="large" className="full"><Fault error={d.error}/><Button icon={<ReloadOutlined/>} onClick={d.refresh}>Обновить</Button><div className="dk-grid-auto" aria-busy={d.loading}>{Object.entries(labels).map(([key,label])=><StatCard key={key} label={label} value={d.loading?'…':d.data?.[key as keyof Dashboard]??'—'}/>)}</div><Alert type="info" showIcon message="Открытые записи Accounting не гарантируют фактическую доступность клиента. NAS в реестре не означает применение к FreeRADIUS."/></Space>
}
