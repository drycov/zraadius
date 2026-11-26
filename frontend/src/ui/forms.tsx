import React,{createContext,useContext,useEffect,useId,useRef,useSyncExternalStore} from 'react';
type Node=React.ReactNode;type Style=React.CSSProperties;type Children={children?:Node;className?:string;style?:Style};
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
