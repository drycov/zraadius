import React,{useEffect,useMemo,useState} from 'react';
import {Alert,App,Button,Card,Checkbox,Col,Form,Input,InputNumber,Modal,Popconfirm,Row,Select,Space,Table,Tag,Typography} from '../ui';
import {ReloadOutlined} from '../ui/icons';
import {type Request,type User,type Group,type Nas,type Session,type Audit,type Dashboard,type Attribute} from '../api';
import {StatCard} from '../vendor/design-kit/components/StatCard';
import MfaPanel from '../MfaPanel';
import {enc,useData,useAction,Fault} from '../hooks';
const {Text}=Typography;
export default function Dictionary({request}:{request:Request}){const d=useData<Attribute[]>(request,'dictionaries');return <Space direction="vertical" className="full"><Fault error={d.error}/><Table<Attribute> rowKey="name" loading={d.loading} dataSource={d.data??[]} columns={[{title:'Атрибут',dataIndex:'name'},{title:'Vendor ID',dataIndex:'vendor'},{title:'Тип',dataIndex:'type'},{title:'List',dataIndex:'list'}]}/></Space>}
