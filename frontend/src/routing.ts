import {useEffect,useState} from 'react';
const routes=new Set(['ppp','overview','users','groups','nas','accounting','audit','dictionary','services','policies','ipoe','ipam','hotspot','device','pki','proxy','iam','account']);
function read(){const route=location.hash.replace(/^#\/?/,'');return routes.has(route)?route:'overview'}
export function useRoute():[string,(page:string)=>void]{const [page,setPage]=useState(read);useEffect(()=>{const update=()=>setPage(read());window.addEventListener('hashchange',update);return()=>window.removeEventListener('hashchange',update)},[]);return [page,(next)=>{if(routes.has(next)){location.hash='/'+next;setPage(next)}}]}
