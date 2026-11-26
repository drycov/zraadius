import {useEffect,useState} from 'react';
import {App} from './ui';
import type {Request} from './api';
import {Alert as KitAlert} from './vendor/design-kit/components/Alert';
export const enc=encodeURIComponent;
export function useData<T>(request:Request,path:string){
 const [data,setData]=useState<T>();
 const [error,setError]=useState('');
 const [loading,setLoading]=useState(true);
 const [revision,reload]=useState(0);
 useEffect(()=>{let active=true;setLoading(true);setError('');request<T>(path).then(v=>{if(active)setData(v)}).catch(e=>{if(active){setError(String(e.message));setData(undefined)}}).finally(()=>{if(active)setLoading(false)});return()=>{active=false}},[request,path,revision]);
 return {data,error,loading,refresh:()=>reload(v=>v+1)};
}
export function Fault({error}:{error:string}){return error?<KitAlert tone="error">{error}</KitAlert>:null}
export function useAction(refresh:()=>void){const {message}=App.useApp();const [busy,setBusy]=useState(false);return {busy,run:async(fn:()=>Promise<unknown>,done?:()=>void)=>{setBusy(true);try{await fn();message.success('Изменения сохранены');done?.();refresh()}catch(e){message.error(e instanceof Error?e.message:'Ошибка запроса')}finally{setBusy(false)}}}}
