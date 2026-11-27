import {useState} from 'react';
import {Alert,Button,Select,Space,Table,Tag} from '../ui';
import {useData,Fault} from '../hooks';
import type {Request,Nas} from '../api';
const services=['device-aaa','l2tp','pppoe','hotspot','dot1x','wpa-enterprise'];
type Rule={id:number;source:string;group_name:string|null;service:string|null;nas_id:number|null;effect:'ALLOW'|'DENY';scope:string;matched:boolean;exclusion_reasons:string[];reason:string};
type Decision={identity_id:number;service:string;nas:{id:number;shortname:string};nas_service_configured:boolean;decision:'ALLOW'|'DENY'|'EXISTING_POLICY';reasons:string[];decisive_rule_ids:number[];baseline_status:string;baseline:{assigned:boolean;enabled:boolean;credential_ready:boolean;reasons:string[]};matches:{items:Rule[];matched_count:number;allow_rule_ids:number[];deny_rule_ids:number[];mixed_effects:boolean};runtime_enforced:boolean};
const reasons:Record<string,string>={identity_disabled:'УЗ заблокирована',identity_expired:'Срок действия истёк',service_not_assigned:'Услуга не назначена',service_disabled:'Услуга отключена',credential_missing:'Реквизиты не готовы',no_effective_nas:'Нет эффективного NAS',nas_or_policy_ineligible:'NAS или назначение не соответствует',nas_service_not_configured:'Услуга не настроена на NAS',explicit_deny:'Явный запрет',baseline_not_configured:'Базовая конфигурация недоступна',rule_disabled:'Правило отключено',service_mismatch:'Другая услуга',nas_mismatch:'Другой NAS'};
const explain=(r:string)=>reasons[r]??r;
function Result({request,id,service,nas}:{request:Request;id:number;service:string;nas:string}){
 const d=useData<Decision>(request,'identities/'+id+'/policy-decision?service='+encodeURIComponent(service)+'&nas_id='+encodeURIComponent(nas));
 const [onlyMatched,setOnlyMatched]=useState('all');
 const result=d.data;
 return <Space direction="vertical" className="full"><Fault error={d.error}/><Button disabled={d.loading} onClick={d.refresh}>Повторить проверку</Button>
 {d.loading&&<span>Вычисление решения...</span>}
 {result&&<><Space wrap><Tag color={result.decision==='DENY'?'red':result.decision==='ALLOW'?'green':'blue'}>{result.decision}</Tag><Tag>{result.nas.shortname}</Tag><Tag>{result.service}</Tag></Space>
 <Alert type={result.decision==='DENY'?'warning':'info'} message={result.reasons.map(explain).join('; ')||'Базовые условия конфигурации выполнены; аутентификация обязательна.'}/>
 <strong>Базовая конфигурация</strong><Space wrap><Tag>Назначение: {result.baseline.assigned?'Да':'Нет'}</Tag><Tag>Услуга: {result.baseline.enabled?'Включена':'Отключена'}</Tag><Tag>Реквизиты: {result.baseline.credential_ready?'Готовы':'Нет'}</Tag><Tag>NAS Service: {result.nas_service_configured?'Да':'Нет'}</Tag></Space>
 <strong>Централизованные правила</strong><Space wrap><Tag>Совпадений: {result.matches.matched_count}</Tag><Tag color="green">ALLOW: {result.matches.allow_rule_ids.length}</Tag><Tag color="red">DENY: {result.matches.deny_rule_ids.length}</Tag></Space>
 {result.matches.mixed_effects&&<Alert type="warning" message="Конфликт ALLOW/DENY: явный запрет имеет приоритет."/>}
 <Select value={onlyMatched} onChange={v=>setOnlyMatched(String(v))} options={[{value:'all',label:'Все правила'},{value:'matched',label:'Только применимые'}]}/>
 <Table<Rule> rowKey="id" pagination={false} dataSource={result.matches.items.filter(r=>onlyMatched==='all'||r.matched)} columns={[{title:'ID',dataIndex:'id'},{title:'Источник',render:(_,r)=>r.group_name??r.source},{title:'Effect',render:(_,r)=><Tag color={r.effect==='DENY'?'red':'green'}>{r.effect}</Tag>},{title:'Услуга',render:(_,r)=>r.service??'Все'},{title:'NAS',render:(_,r)=>r.nas_id??'Все'},{title:'Результат',render:(_,r)=>result.decisive_rule_ids.includes(r.id)?'Определяющее':r.matched?'Применимо':r.exclusion_reasons.map(explain).join('; ')},{title:'Обоснование',dataIndex:'reason'}]}/>
 </>}
 </Space>
}
export default function IdentityPolicySimulator({request,id}:{request:Request;id:number}){
 const n=useData<Nas[]>(request,'nas');
 const [service,setService]=useState(services[0]);
 const [nas,setNas]=useState('none');
 const [submitted,setSubmitted]=useState<{service:string;nas:string;run:number}>();
 const valid=nas!=='none'&&!!n.data?.some(x=>String(x.id)===nas);
 return <Space direction="vertical" className="full"><Alert type="info" message="Симулятор конфигурации. Не выполняет RADIUS-аутентификацию и не изменяет права доступа."/><Fault error={n.error}/>
 <Space wrap><Select value={service} onChange={v=>{setService(String(v));setSubmitted(undefined)}} options={services.map(v=>({value:v,label:v}))}/><Select value={nas} onChange={v=>{setNas(String(v));setSubmitted(undefined)}} options={[{value:'none',label:'Выберите NAS'},...(n.data??[]).map(x=>({value:String(x.id),label:x.shortname+' ('+x.nasname+')'}))]}/><Button type="primary" disabled={!valid||n.loading} onClick={()=>setSubmitted(old=>({service,nas,run:(old?.run??0)+1}))}>Вычислить решение</Button></Space>
 {submitted&&<Result key={id+':'+submitted.service+':'+submitted.nas+':'+submitted.run} request={request} id={id} service={submitted.service} nas={submitted.nas}/>}
 </Space>
}
