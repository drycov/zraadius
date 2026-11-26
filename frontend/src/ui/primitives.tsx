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
