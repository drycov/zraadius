import {useEffect,useId,useState,type ReactNode} from 'react';

type Item={key:string;label:string;icon?:ReactNode};
type Section={key:string;label:string;icon:ReactNode;routes:string[]};
const sections:Section[]=[
 {key:'vpn',label:'PPP / VPN',icon:<NavIcon kind="shield"/>,routes:['ppp']},
 {key:'subscribers',label:'Абоненты и доступ',icon:<NavIcon kind="users"/>,routes:['users','groups','hotspot','ipoe']},
 {key:'network',label:'Сетевая инфраструктура',icon:<NavIcon kind="network"/>,routes:['nas','ipam','device']},
 {key:'radius',label:'RADIUS / AAA',icon:<NavIcon kind="shield"/>,routes:['services','policies','dictionary','proxy','pki']},
 {key:'monitoring',label:'Мониторинг и аудит',icon:<NavIcon kind="activity"/>,routes:['accounting','audit']},
 {key:'admin',label:'Администрирование',icon:<NavIcon kind="settings"/>,routes:['iam','account']},
];
function NavIcon({kind}:{kind:string}){
 const paths:Record<string,ReactNode>={
 users:<><circle cx="9" cy="8" r="3"/><path d="M2 21v-2a7 7 0 0 1 14 0v2M16 5a3 3 0 0 1 0 6m2 3a6 6 0 0 1 4 5v2"/></>,
 network:<><rect x="9" y="2" width="6" height="5" rx="1"/><rect x="2" y="17" width="6" height="5" rx="1"/><rect x="16" y="17" width="6" height="5" rx="1"/><path d="M12 7v5H5v5m7-5h7v5"/></>,
 shield:<><path d="m12 2 9 4v6c0 5-4 8-9 10-5-2-9-5-9-10V6z"/><path d="m8 12 3 3 5-6"/></>,
 activity:<path d="M2 12h5l3-8 4 16 3-8h5"/>,
 settings:<><circle cx="12" cy="12" r="3"/><path d="M12 2v4m0 12v4M2 12h4m12 0h4M5 5l3 3m8 8 3 3M19 5l-3 3m-8 8-3 3"/></>,
 };
 return <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">{paths[kind]}</svg>
}
const storageKey='zradius.sidebar.groups.v1';
function readExpanded():string[]{
 try{const raw:unknown=JSON.parse(localStorage.getItem(storageKey)??'[]');return Array.isArray(raw)?raw.filter((v):v is string=>typeof v==='string'&&sections.some(s=>s.key===v)):[]}catch{return []}
}
function Chevron(){return <svg aria-hidden="true" className="zr-nav-chevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m6 9 6 6 6-6"/></svg>}
export default function SidebarNav({items,active,onNavigate}:{items:Item[];active:string;onNavigate:(key:string)=>void}){
 const uid=useId();
 const activeGroup=sections.find(s=>s.routes.includes(active))?.key;
 const [expanded,setExpanded]=useState(()=>Array.from(new Set([...readExpanded(),...(activeGroup?[activeGroup]:[])])));
 const [mobileOpen,setMobileOpen]=useState(false);
 useEffect(()=>{if(activeGroup)setExpanded(prev=>prev.includes(activeGroup)?prev:[...prev,activeGroup]);setMobileOpen(false)},[active,activeGroup]);
 useEffect(()=>{try{localStorage.setItem(storageKey,JSON.stringify(expanded))}catch{/* storage unavailable */}},[expanded]);
 const lookup=new Map(items.map(item=>[item.key,item]));
 const navigate=(key:string)=>{setMobileOpen(false);onNavigate(key)};
 const item=(entry:Item)=> <button type="button" key={entry.key} className={'dk-nav-link '+(entry.key===active?'is-active':'')} aria-current={entry.key===active?'page':undefined} onClick={()=>navigate(entry.key)}>{entry.icon}<span>{entry.label}</span></button>;
 const assigned=new Set(sections.flatMap(s=>s.routes));
 return <div className="zr-sidebar-menu">
  <button type="button" className="zr-mobile-nav-toggle" aria-expanded={mobileOpen} aria-controls={uid+'-nav'} onClick={()=>setMobileOpen(v=>!v)}><span>Навигация</span><Chevron/></button>
  <nav id={uid+'-nav'} className={'dk-sidebar__nav zr-grouped-nav '+(mobileOpen?'is-mobile-open':'')} aria-label="Основная навигация">
   {items.filter(x=>!assigned.has(x.key)).map(item)}
   {sections.map(section=>{
    const children=section.routes.map(key=>lookup.get(key)).filter((v):v is Item=>!!v);
    if(!children.length)return null;
    const open=expanded.includes(section.key);
    const selected=children.some(x=>x.key===active);
    const id=uid+'-'+section.key;
    return <section key={section.key} className={'zr-nav-group '+(selected?'has-active':'')}>
     <button id={id+'-trigger'} type="button" className="zr-nav-group-trigger" aria-expanded={open} aria-controls={id+'-items'} onClick={()=>setExpanded(prev=>open?prev.filter(x=>x!==section.key):[...prev,section.key])}>{section.icon}<span>{section.label}</span><Chevron/></button>
     <div id={id+'-items'} className="zr-nav-group-items" role="group" aria-labelledby={id+'-trigger'} hidden={!open}>{children.map(item)}</div>
    </section>
   })}
  </nav>
 </div>
}
