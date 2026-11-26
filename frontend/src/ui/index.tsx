import React,{createContext,useContext,useEffect,useId,useMemo,useRef,useState,useSyncExternalStore} from 'react';
import {createPortal} from 'react-dom';
import QR from 'qrcode';
import {Button as KitButton} from '../vendor/design-kit/components/Button';
import {Card as KitCard} from '../vendor/design-kit/components/Card';
import {Badge} from '../vendor/design-kit/components/Badge';
import {Spinner} from '../vendor/design-kit/components/Spinner';
import {EmptyState} from '../vendor/design-kit/components/EmptyState';
import {Alert as KitAlert} from '../vendor/design-kit/components/Alert';
type Node=React.ReactNode;
type Style=React.CSSProperties;
type Children={children?:Node;className?:string;style?:Style};
export function Button({type,htmlType,danger,loading,block,icon,children,className='',disabled,...rest}:Omit<React.ButtonHTMLAttributes<HTMLButtonElement>,'type'> & {type?:'primary'|'default';htmlType?:'button'|'submit'|'reset';danger?:boolean;loading?:boolean;block?:boolean;icon?:Node}){
 return <KitButton {...rest} type={htmlType??'button'} variant={danger?'danger':type==='primary'?'primary':'secondary'} disabled={disabled||loading} aria-busy={loading} className={className+(block?' zr-block':'')}>{loading?<Spinner label="Загрузка"/>:icon}{children}</KitButton>
}
export function Card({title,extra,children,className='',style}:Children&{title?:Node;extra?:Node;loading?:boolean}){return <div className={className} style={style}><KitCard title={title||extra?<div className="zr-card-head"><span>{title}</span>{extra}</div>:undefined}>{children}</KitCard></div>}
export function Alert({type='info',message,description}: {type?:'error'|'warning'|'info'|'success';message?:Node;description?:Node;showIcon?:boolean}){return type==='error'?<KitAlert tone="error">{message}{description&&<div>{description}</div>}</KitAlert>:<div className={'zr-alert zr-alert-'+type} role="status"><strong>{message}</strong>{description&&<div>{description}</div>}</div>}
export function Tag({color,children}: {color?:string;children?:Node}){return <Badge tone={color==='green'?'online':color==='red'?'offline':color==='orange'?'warning':'unknown'}>{children}</Badge>}
export const Spin=Spinner;
export function Space({direction,wrap,size,children,className='',style}:Children&{direction?:'vertical'|'horizontal';wrap?:boolean;size?:string|number}){return <div className={'zr-space '+(direction==='vertical'?'zr-stack':'')+' '+className} style={{gap:typeof size==='number'?size:size==='large'?20:12,flexWrap:wrap?'wrap':undefined,...style}}>{children}</div>}
export function Row({gutter,children}:Children&{gutter?:number|number[]}){return <div className="zr-grid" style={{gap:Array.isArray(gutter)?gutter[0]:gutter??12}}>{children}</div>}
export function Col({xs,md,span,children}:Children&{xs?:number;md?:number;span?:number;sm?:number;xl?:number}){return <div className="zr-col" style={{'--zr-xs':xs??span??24,'--zr-md':md??span??xs??24} as Style}>{children}</div>}
type Values=Record<string,any>;
type Rule={required?:boolean;min?:number;max?:number;pattern?:RegExp;message?:string};
type Field={name:string;rules:Rule[];child:React.ReactElement};
function makeForm(){
 let values:Values={},initial:Values={},errors:Record<string,string>={},revision=0,initialized=false,submitter:()=>void=()=>{};const listeners=new Set<()=>void>();const fields=new Map<string,Field>();
 const notify=()=>{revision++;listeners.forEach(fn=>fn())};
 return {subscribe:(fn:()=>void)=>{listeners.add(fn);return()=>{listeners.delete(fn)}},snapshot:()=>revision,values:()=>values,errors:()=>errors,fields,
 init:(v:Values)=>{initial={...v};if(!initialized){values={...initial,...values};initialized=true}},
 set:(name:string,v:unknown)=>{values={...values,[name]:v};errors={...errors,[name]:''};notify()},
 setFieldsValue:(v:Values)=>{values={...values,...v};errors={};notify()},
 resetFields:()=>{values={...initial};errors={};notify()},
 validate:()=>{const result:Values={};const next:Record<string,string>={};for(const [name,f] of fields){const v=values[name];result[name]=v;const empty=v===undefined||v===null||v===''||(Array.isArray(v)&&!v.length);for(const rule of f.rules){if(rule.required&&empty){next[name]=rule.message??'Обязательное поле';break}if(!empty&&((rule.min!==undefined&&String(v).length<rule.min)||(rule.max!==undefined&&String(v).length>rule.max)||(rule.pattern&&!rule.pattern.test(String(v))))){next[name]=rule.message??'Проверьте значение';break}}}errors=next;notify();return Object.keys(next).length?null:result},
 bind:(fn:()=>void)=>{submitter=fn;return()=>{submitter=()=>{}}},submit:()=>submitter()};
}
type FormInstance=ReturnType<typeof makeForm>;
const FormContext=createContext<{form:FormInstance;disabled:boolean}|null>(null);
function useForm():[FormInstance]{const ref=useRef<FormInstance>();if(!ref.current)ref.current=makeForm();return [ref.current]}
function FormBase({form:external,initialValues,layout,disabled=false,onFinish,children,style}:Children&{form?:FormInstance;initialValues?:Values;layout?:'inline'|'vertical';disabled?:boolean;onFinish?:(v:Values)=>unknown}){
 const [local]=useForm();const form=external??local;const ref=useRef<HTMLFormElement>(null);form.init(initialValues??{});
 useEffect(()=>form.bind(()=>ref.current?.requestSubmit()),[form]);
 return <FormContext.Provider value={{form,disabled}}><form ref={ref} className={'zr-form '+(layout==='inline'?'zr-form-inline':'')} style={style} onSubmit={e=>{e.preventDefault();if(disabled)return;const v=form.validate();if(v)void onFinish?.(v)}}>{children}</form></FormContext.Provider>
}
function FormItem({name,label,rules=[],valuePropName,children}:{name:string;label?:Node;rules?:Rule[];valuePropName?:'checked';children:React.ReactElement}){
 const ctx=useContext(FormContext);if(!ctx)throw new Error('Form.Item outside Form');const {form,disabled}=ctx;const id=useId();
 useSyncExternalStore(form.subscribe,form.snapshot,form.snapshot);
 useEffect(()=>{form.fields.set(name,{name,rules,child:children});return()=>{form.fields.delete(name)}},[form,name,rules,children]);
 const v=form.values()[name];const error=form.errors()[name];const checked=valuePropName==='checked';const child=React.cloneElement(children,{id,name,disabled:disabled||children.props.disabled,'aria-invalid':!!error,'aria-describedby':error?id+'-error':undefined,...(checked?{checked:v??false}:{value:v??''}),onChange:(arg:any)=>{const next=arg?.target?(checked?arg.target.checked:arg.target.value):arg;form.set(name,next);children.props.onChange?.(arg)}});
 return <div className="zr-field">{label&&<label className="dk-label" htmlFor={id}>{label}</label>}{child}{error&&<div id={id+'-error'} className="dk-text-danger" role="alert">{error}</div>}</div>
}
export const Form=Object.assign(FormBase,{Item:FormItem,useForm});
function InputBase(props:React.InputHTMLAttributes<HTMLInputElement>){return <input {...props} className={'dk-input '+(props.className??'')}/>}
function Password(props:React.InputHTMLAttributes<HTMLInputElement>){return <InputBase {...props} type="password"/>}
function TextArea(props:React.TextareaHTMLAttributes<HTMLTextAreaElement>){return <textarea {...props} className={'dk-input '+(props.className??'')}/>}
export const Input=Object.assign(InputBase,{Password,Search:InputBase,TextArea});
export function InputNumber({value,onChange,min,max,...rest}:Omit<React.InputHTMLAttributes<HTMLInputElement>,'onChange'|'value'> & {value?:number|string|null;onChange?:(v:number|null)=>void}){return <InputBase {...rest} type="number" min={min} max={max} value={value??''} onChange={e=>onChange?.(e.target.value===''?null:e.target.valueAsNumber)}/>}
export function Checkbox({children,...props}:React.InputHTMLAttributes<HTMLInputElement>){return <label className="zr-checkbox"><input {...props} type="checkbox"/>{children}</label>}
type Option={value:string|number;label:Node};
export function Select({options=[],value,onChange,mode,placeholder,allowClear,disabled,style,id,name}: {options?:Option[];value?:any;onChange?:(v:any)=>void;mode?:'multiple';placeholder?:string;allowClear?:boolean;disabled?:boolean;style?:Style;id?:string;name?:string}){
 const multiple=mode==='multiple';const index=(v:any)=>{const i=options.findIndex(o=>o.value===v);return i<0?'':String(i)};
 return <select id={id} name={name} className="dk-input zr-select" multiple={multiple} disabled={disabled} style={style} value={multiple?(Array.isArray(value)?value.map(index).filter(Boolean):[]):index(value)} onChange={e=>{if(multiple)onChange?.(Array.from(e.target.selectedOptions).map(o=>options[Number(o.value)].value));else onChange?.(e.target.value===''?undefined:options[Number(e.target.value)].value)}}>{!multiple&&<option value="" disabled={!allowClear}>{placeholder??'Выберите значение'}</option>}{options.map((o,i)=><option key={String(o.value)} value={String(i)}>{o.label}</option>)}</select>
}
type Column<T>={title?:Node;dataIndex?:keyof T|string;render?:(value:any,row:T,index:number)=>Node;key?:string; width?:number};
export function Table<T>({rowKey,dataSource=[],columns,loading,pagination,scroll}: {rowKey:keyof T|string|((row:T)=>React.Key);dataSource?:T[];columns:Column<T>[];loading?:boolean;pagination?:false|{pageSize?:number};scroll?:{x?:number|string};size?:string}){
 const [page,setPage]=useState(0);const size=typeof pagination==='object'?pagination.pageSize??10:10;const pages=Math.max(1,Math.ceil(dataSource.length/size));const current=Math.min(page,pages-1);const rows=pagination===false?dataSource:dataSource.slice(current*size,(current+1)*size);
 return <div className="zr-table-wrap" aria-busy={loading}>{loading&&<Spinner label="Загрузка таблицы"/>}<div className="zr-table-scroll"><table className="zr-table" style={{minWidth:typeof scroll?.x==='number'?scroll.x:undefined}}><thead><tr>{columns.map((c,i)=><th key={c.key??i} scope="col">{c.title}</th>)}</tr></thead><tbody>{rows.map((row,i)=><tr key={typeof rowKey==='function'?rowKey(row):String((row as any)[rowKey]??i)}>{columns.map((c,j)=>{const v=c.dataIndex===undefined?undefined:(row as any)[c.dataIndex];return <td key={j}>{c.render?c.render(v,row,i):v==null?'—':String(v)}</td>})}</tr>)}</tbody></table>{!loading&&!rows.length&&<EmptyState title="Нет данных"/>}</div>{pagination!==false&&pages>1&&<Space><Button disabled={!current} onClick={()=>setPage(current-1)}>Назад</Button><span>{current+1} / {pages}</span><Button disabled={current+1>=pages} onClick={()=>setPage(current+1)}>Далее</Button></Space>}</div>
}
export function Modal({open,title,children,footer,onCancel,onOk,confirmLoading,cancelButtonProps}:Children&{open:boolean;title?:Node;footer?:Node;onCancel?:()=>void;onOk?:()=>void;confirmLoading?:boolean;destroyOnClose?:boolean;cancelButtonProps?:{style?:Style}}){
 const ref=useRef<HTMLDialogElement>(null);useEffect(()=>{const d=ref.current;if(open&&d&&!d.open)d.showModal();else if(!open&&d?.open)d.close()},[open]);if(!open)return null;
 return createPortal(<dialog ref={ref} className="dk-modal zr-dialog" onCancel={e=>{e.preventDefault();if(!confirmLoading)onCancel?.()}}><div className="dk-modal__head"><h3>{title}</h3><Button disabled={confirmLoading} aria-label="Закрыть" onClick={onCancel}>×</Button></div><div className="dk-modal__body">{children}</div>{footer!==null&&<div className="dk-modal__foot">{footer??<Space><Button style={cancelButtonProps?.style} disabled={confirmLoading} onClick={onCancel}>Отмена</Button><Button type="primary" loading={confirmLoading} onClick={onOk??onCancel}>OK</Button></Space>}</div>}</dialog>,document.body)
}
export function Popconfirm({title,onConfirm,children}:{title:Node;onConfirm:()=>unknown;children:React.ReactElement}){const [open,setOpen]=useState(false);const [busy,setBusy]=useState(false);return <>{React.cloneElement(children,{onClick:(e:any)=>{e.preventDefault();setOpen(true)}})}<Modal open={open} title={title} confirmLoading={busy} onCancel={()=>setOpen(false)} onOk={async()=>{setBusy(true);try{await onConfirm();setOpen(false)}finally{setBusy(false)}}}><p>Подтвердите действие.</p></Modal></>}
function Text({children,type,copyable,style}:Children&{type?:'secondary';copyable?:boolean|{text:string}}){const [copied,setCopied]=useState(false);return <span className={type==='secondary'?'zr-muted':''} style={style}>{children}{copyable&&<Button onClick={async()=>{try{await navigator.clipboard.writeText(typeof copyable==='object'?copyable.text:String(children));setCopied(true)}catch{setCopied(false)}}}>{copied?'Скопировано':'Копировать'}</Button>}</span>}
export const Typography={Text,Paragraph:Text};
export function QRCode({value,size=220}: {value:string;size?:number;color?:string;bgColor?:string;bordered?:boolean}){const ref=useRef<HTMLCanvasElement>(null);const [error,setError]=useState(false);useEffect(()=>{if(ref.current)void QR.toCanvas(ref.current,value,{width:size,margin:4,errorCorrectionLevel:'M'}).catch(()=>setError(true))},[value,size]);return error?<Alert type="error" message="QR недоступен — используйте ручной ключ"/>:<canvas ref={ref} aria-label="QR-код настройки MFA"/>}
type Message={success:(s:string)=>void;warning:(s:string)=>void;error:(s:string)=>void};
const MessageContext=createContext<{message:Message}>({message:{success:()=>{},warning:()=>{},error:()=>{}}});
function AppBase({children}:Children){const [toast,setToast]=useState<{kind:'success'|'warning'|'error';text:string;id:number}>();const message=useMemo(()=>({success:(text:string)=>setToast({kind:'success',text,id:Date.now()}),warning:(text:string)=>setToast({kind:'warning',text,id:Date.now()}),error:(text:string)=>setToast({kind:'error',text,id:Date.now()})}),[]);useEffect(()=>{if(!toast)return;const timer=window.setTimeout(()=>setToast(undefined),5000);return()=>clearTimeout(timer)},[toast]);return <MessageContext.Provider value={{message}}>{children}{toast&&<div className="zr-toast"><Alert type={toast.kind} message={toast.text}/></div>}</MessageContext.Provider>}
export const App=Object.assign(AppBase,{useApp:()=>useContext(MessageContext)});
function LayoutBase({children,className=''}:Children){return <div className={'zr-layout '+className}>{children}</div>}
function Sider({children}:Children&{breakpoint?:string;collapsedWidth?:string;width?:number}){return <aside className="dk-sidebar zr-sidebar">{children}</aside>}
function Header({children,className=''}:Children){return <header className={className}>{children}</header>}
function Content({children,className=''}:Children){return <main className={className}>{children}</main>}
export const Layout=Object.assign(LayoutBase,{Header,Sider,Content});
export function Menu({items,selectedKeys,onClick}: {items:{key:string;label:Node;icon?:Node}[];selectedKeys:string[];onClick:(e:{key:string})=>void;mode?:string}){return <nav className="dk-sidebar__nav" aria-label="Основная навигация">{items.map(i=><button type="button" key={i.key} className={'dk-nav-link '+(selectedKeys.includes(i.key)?'is-active':'')} aria-current={selectedKeys.includes(i.key)?'page':undefined} onClick={()=>onClick({key:i.key})}>{i.icon}{i.label}</button>)}</nav>}
