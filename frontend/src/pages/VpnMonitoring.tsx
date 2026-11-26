import {useEffect,useState} from 'react';
import {Alert,Button,Checkbox,Space,Table,Tag} from '../ui';
import Disclosure from '../ui/Disclosure';
import {StatCard} from '../vendor/design-kit/components/StatCard';
import {useData,Fault} from '../hooks';
import type {Request} from '../api';
type NasRow={address:string;name:string;open_records:number;needs_review:number;rx_bytes:string;tx_bytes:string};
type Dashboard={generated_at:string;inventory:{users:number;enabled_users:number;static_users:number;profiles:number;groups:number;pools:number;configured_nas:number};sessions:{recorded:number;reported_open:number;stale:number;unknown:number;closed:number;starts_24h:number;stops_24h:number;open_rx_bytes:string;open_tx_bytes:string;last_accounting:string|null};by_nas:NasRow[];disconnect_24h:{status:string;count:number}[]};
function bytes(v:string|undefined){if(v===undefined)return '—';return new Intl.NumberFormat('ru',{maximumFractionDigits:2}).format(Number(v)/1073741824)+' GiB'}
function Monitor({request}:{request:Request}){
 const d=useData<Dashboard>(request,'ppp/monitoring');const [auto,setAuto]=useState(false);const x=d.data;
 useEffect(()=>{if(!auto)return;const t=window.setInterval(()=>{if(document.visibilityState==='visible')d.refresh()},60000);return()=>window.clearInterval(t)},[auto,request]);
 const cards:[string,number|string|undefined][]=[['VPN-пользователи',x?.inventory.users],['Разрешённые',x?.inventory.enabled_users],['Статические IP',x?.inventory.static_users],['NAS с L2TP',x?.inventory.configured_nas],['Без Stop, свежие',x?.sessions.reported_open],['Устаревшие',x?.sessions.stale],['Без Interim',x?.sessions.unknown],['Start за 24ч',x?.sessions.starts_24h],['Stop за 24ч',x?.sessions.stops_24h],['RX открытых записей',bytes(x?.sessions.open_rx_bytes)],['TX открытых записей',bytes(x?.sessions.open_tx_bytes)],['Всего записей',x?.sessions.recorded]];
 return <Space direction="vertical" className="full"><Fault error={d.error}/><Alert type="info" message="Данные RADIUS Accounting, не опрос NAS. Открытая запись не гарантирует доступность VPN. Трафик накопленный за открытые сессии, не скорость и не расход за сутки."/>
 <Space wrap><Button onClick={d.refresh} disabled={d.loading}>Обновить</Button><Checkbox checked={auto} onChange={e=>setAuto(e.target.checked)}>Автообновление 60 сек</Checkbox><span>Снимок: {x?new Date(x.generated_at).toLocaleString():'—'}</span></Space>
 <div className="dk-grid-auto" aria-busy={d.loading}>{cards.map(([label,value])=><StatCard key={label} label={label} value={d.loading?'…':value??'—'}/>)}</div>
 <span>Последний Accounting: {x?.sessions.last_accounting?new Date(x.sessions.last_accounting).toLocaleString():'—'}</span>
 <Disclosure title="Распределение открытых записей по NAS" defaultOpen><Table<NasRow> rowKey="address" loading={d.loading} dataSource={x?.by_nas??[]} columns={[{title:'NAS',dataIndex:'name'},{title:'IPv4',dataIndex:'address'},{title:'Без Stop',dataIndex:'open_records'},{title:'Требуют проверки',render:(_,r)=><Tag color={r.needs_review?'orange':'green'}>{r.needs_review}</Tag>},{title:'RX',render:(_,r)=>bytes(r.rx_bytes)},{title:'TX',render:(_,r)=>bytes(r.tx_bytes)}]}/></Disclosure>
 <Disclosure title="Disconnect за 24 часа" defaultOpen><Space wrap>{['ack','nak','unknown','pending'].map(status=><Tag key={status} color={status==='ack'?'green':status==='nak'?'red':'orange'}>{status.toUpperCase()}: {x?x.disconnect_24h.find(r=>r.status===status)?.count??0:'—'}</Tag>)}</Space></Disclosure></Space>
}
export default function VpnMonitoring({request}:{request:Request}){return <Disclosure title="VPN Monitoring Dashboard" defaultOpen><Monitor request={request}/></Disclosure>}
