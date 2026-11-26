import React,{useState} from 'react';
import {Spinner} from '../vendor/design-kit/components/Spinner';
import {EmptyState} from '../vendor/design-kit/components/EmptyState';
import {Button,Space} from './primitives';
type Node=React.ReactNode;
type Column<T>={title?:Node;dataIndex?:keyof T|string;render?:(value:any,row:T,index:number)=>Node;key?:string; width?:number};
export function Table<T>({rowKey,dataSource=[],columns,loading,pagination,scroll}: {rowKey:keyof T|string|((row:T)=>React.Key);dataSource?:T[];columns:Column<T>[];loading?:boolean;pagination?:false|{pageSize?:number};scroll?:{x?:number|string};size?:string}){
 const [page,setPage]=useState(0);const size=typeof pagination==='object'?pagination.pageSize??10:10;const pages=Math.max(1,Math.ceil(dataSource.length/size));const current=Math.min(page,pages-1);const rows=pagination===false?dataSource:dataSource.slice(current*size,(current+1)*size);
 return <div className="zr-table-wrap" aria-busy={loading}>{loading&&<Spinner label="Загрузка таблицы"/>}<div className="zr-table-scroll"><table className="zr-table" style={{minWidth:typeof scroll?.x==='number'?scroll.x:undefined}}><thead><tr>{columns.map((c,i)=><th key={c.key??i} scope="col">{c.title}</th>)}</tr></thead><tbody>{rows.map((row,i)=><tr key={typeof rowKey==='function'?rowKey(row):String((row as any)[rowKey]??i)}>{columns.map((c,j)=>{const v=c.dataIndex===undefined?undefined:(row as any)[c.dataIndex];return <td key={j}>{c.render?c.render(v,row,i):v==null?'—':String(v)}</td>})}</tr>)}</tbody></table>{!loading&&!rows.length&&<EmptyState title="Нет данных"/>}</div>{pagination!==false&&pages>1&&<Space><Button disabled={!current} onClick={()=>setPage(current-1)}>Назад</Button><span>{current+1} / {pages}</span><Button disabled={current+1>=pages} onClick={()=>setPage(current+1)}>Далее</Button></Space>}</div>
}
