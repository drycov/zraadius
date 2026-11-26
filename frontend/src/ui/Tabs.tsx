import {useId,useState,useRef,type ReactNode,type KeyboardEvent} from 'react';
import {PlainSections} from './Disclosure';

export type TabItem={id:string;label:string;content:ReactNode};
type Props={items:TabItem[];label:string;active?:string;onChange?:(id:string)=>void;defaultActive?:string;plainSections?:boolean};
export default function Tabs({items,label,active,onChange,defaultActive,plainSections=true}:Props){
 const uid=useId();const [local,setLocal]=useState(defaultActive??items[0]?.id);const [visited,setVisited]=useState<string[]>([]);const refs=useRef<Record<string,HTMLButtonElement|null>>({});
 const selected=items.some(x=>x.id===(active??local))?(active??local):items[0]?.id;
 const select=(id:string)=>{setVisited(old=>old.includes(id)?old:[...old,id]);if(selected)setVisited(old=>old.includes(selected)?old:[...old,selected]);if(active===undefined)setLocal(id);onChange?.(id)};
 const keyDown=(e:KeyboardEvent<HTMLButtonElement>,index:number)=>{let next=index;if(e.key==='ArrowRight')next=(index+1)%items.length;else if(e.key==='ArrowLeft')next=(index-1+items.length)%items.length;else if(e.key==='Home')next=0;else if(e.key==='End')next=items.length-1;else return;e.preventDefault();select(items[next].id);refs.current[items[next].id]?.focus()};
 return <div className="zr-tabs"><div role="tablist" aria-label={label} className="zr-tablist">{items.map((x,i)=><button key={x.id} ref={el=>{refs.current[x.id]=el}} type="button" role="tab" id={uid+'-tab-'+x.id} aria-controls={uid+'-panel-'+x.id} aria-selected={selected===x.id} tabIndex={selected===x.id?0:-1} onClick={()=>select(x.id)} onKeyDown={e=>keyDown(e,i)}>{x.label}</button>)}</div>{items.map(x=><div key={x.id} role="tabpanel" id={uid+'-panel-'+x.id} aria-labelledby={uid+'-tab-'+x.id} hidden={selected!==x.id} className="zr-tabpanel">{(selected===x.id||visited.includes(x.id))&&(plainSections?<PlainSections>{x.content}</PlainSections>:x.content)}</div>)}</div>
}
