import {createContext,useContext,useId,useState,type ReactNode} from 'react';

const PlainContext=createContext(false);
export function PlainSections({children}:{children:ReactNode}){return <PlainContext.Provider value={true}>{children}</PlainContext.Provider>}
type Props={title:string;description?:string;meta?:string;children:ReactNode;open?:boolean;onToggle?:(open:boolean)=>void;defaultOpen?:boolean};
export default function Disclosure({title,description,meta,children,open,onToggle,defaultOpen=false}:Props){
 const [local,setLocal]=useState(defaultOpen);
 const expanded=open??local;
 const id=useId();
 const plain=useContext(PlainContext);
 if(plain&&open===undefined)return <section className="zr-plain-section"><header className="zr-section-heading"><h3>{title}</h3>{meta&&<span>{meta}</span>}{description&&<p>{description}</p>}</header><div className="zr-section-body">{children}</div></section>;
 return <section className="zr-disclosure">
  <button type="button" className="zr-disclosure-trigger" id={id+'-trigger'} aria-expanded={expanded} aria-controls={id+'-panel'} onClick={()=>{if(open===undefined)setLocal(!expanded);onToggle?.(!expanded)}}>
   <span className="zr-disclosure-symbol" aria-hidden="true"><svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M3 6a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/></svg></span>
   <span className="zr-disclosure-label"><strong>{title}</strong>{description&&<small>{description}</small>}</span>
   {meta&&<span className="zr-disclosure-meta">{meta}</span>}
   <svg className="zr-disclosure-chevron" aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m6 9 6 6 6-6"/></svg>
  </button>
  <div id={id+'-panel'} role="region" aria-labelledby={id+'-trigger'} hidden={!expanded} className="zr-disclosure-panel">{expanded?children:null}</div>
 </section>
}
export function GroupList<T extends {id:number|string;name:string;description?:string}>({items,loading,render}:{items:T[];loading:boolean;render:(item:T)=>ReactNode}){
 const [selected,setSelected]=useState<number|string>();
 const [query,setQuery]=useState('');
 const visible=items.filter(x=>(x.name+' '+(x.description??'')).toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()));
 return <div className="zr-group-list">
  <div className="zr-group-toolbar"><input className="dk-input" type="search" aria-label="Поиск групп" placeholder="Поиск по имени или описанию" value={query} onChange={e=>setQuery(e.target.value)}/><span className="zr-muted">{visible.length} / {items.length}</span></div>
  {loading?<div role="status" className="zr-group-empty">Загрузка групп…</div>:visible.length?visible.map(x=><Disclosure key={x.id} title={x.name} description={x.description} open={selected===x.id} onToggle={v=>setSelected(v?x.id:undefined)}>{render(x)}</Disclosure>):<div className="zr-group-empty">{query?'Группы не найдены':'Нет групп. Создайте первую группу.'}</div>}
 </div>
}
