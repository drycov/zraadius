import React,{useEffect,useState} from 'react';
import {Alert,Button,Card,Form,Input,QRCode,Space,Spin,Tag,Typography} from 'antd';
import {ApiError,type Request} from './api';
type Status={enabled:boolean;recovery_remaining:number};
type Enrollment={secret:string;otpauth_uri:string;expires_in:number};
export default function MfaPanel({request}:{request:Request}){
 const [status,setStatus]=useState<Status>();
 const [enrollment,setEnrollment]=useState<Enrollment>();
 const [codes,setCodes]=useState<string[]>();
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState('');
 const [form]=Form.useForm();
 useEffect(()=>{let active=true;request<Status>('iam/mfa/status').then(v=>{if(active)setStatus(v)}).catch(()=>{if(active)setError('Не удалось получить состояние MFA')});return()=>{active=false}},[request]);
 async function submit(v:{password:string;otp?:string}){
  setBusy(true);setError('');
  try{
   if(status?.enabled){await request('iam/mfa/disable','POST',v);window.location.reload();return}
   if(enrollment){const r=await request<{recovery_codes:string[]}>('iam/mfa/confirm','POST',v);setCodes(r.recovery_codes);setEnrollment(undefined);form.resetFields()}
   else{setEnrollment(await request<Enrollment>('iam/mfa/setup','POST',{password:v.password}));form.resetFields()}
  }catch(e){setError(e instanceof ApiError&&e.status===401?'Неверный пароль или код':e instanceof ApiError&&e.status===429?'Слишком много попыток. Повторите через 5 минут.':e instanceof ApiError&&e.status===409?'Настройка истекла или состояние изменилось. Обновите страницу.':'Ошибка операции MFA')}
  finally{setBusy(false)}
 }
 return <Card title="Двухфакторная аутентификация">
 <Space direction="vertical" style={{width:'100%'}} size="middle">
 {error&&<Alert type="error" showIcon message={error}/>}
 {codes?<><Alert type="warning" showIcon message="MFA включена. Все прежние сессии отозваны." description="Сохраните резервные коды в защищённом хранилище. Они отображаются только сейчас."/><Typography.Paragraph copyable={{text:codes.join('\n')}} style={{whiteSpace:'pre-wrap',fontFamily:'monospace'}}>{codes.join('\n')}</Typography.Paragraph><Button type="primary" onClick={()=>window.location.reload()}>Коды сохранены — войти заново</Button></>:!status?<>{!error&&<Spin/>}</>:<>
 <Space><Tag color={status.enabled?'green':'default'}>{status.enabled?'Включена':'Отключена'}</Tag>{status.enabled&&<Typography.Text>Резервных кодов: {status.recovery_remaining}</Typography.Text>}</Space>
 {enrollment&&<><Alert type="info" message="Отсканируйте QR-код приложением-аутентификатором" description="Подтвердите настройку в течение 10 минут."/><QRCode value={enrollment.otpauth_uri} size={220} color="#000000" bgColor="#ffffff" bordered={false}/><Typography.Text copyable>{enrollment.secret}</Typography.Text><Typography.Text type="secondary">Ручной ввод: SHA1, 6 цифр, 30 секунд.</Typography.Text></>}
 <Form form={form} layout="vertical" onFinish={submit}>
 <Form.Item name="password" label="Текущий пароль" rules={[{required:true}]}><Input.Password autoComplete="current-password" maxLength={128}/></Form.Item>
 {(enrollment||status.enabled)&&<Form.Item name="otp" label={status.enabled?'TOTP или резервный код':'Код TOTP'} rules={[{required:true},...(enrollment?[{pattern:/^[0-9]{6}$/,message:'Введите 6 цифр'}]:[])]}><Input autoComplete="one-time-code" maxLength={64}/></Form.Item>}
 <Space><Button htmlType="submit" type="primary" danger={status.enabled} loading={busy}>{status.enabled?'Отключить MFA':enrollment?'Подтвердить MFA':'Настроить MFA'}</Button>{enrollment&&<Button disabled={busy} onClick={()=>{setEnrollment(undefined);form.resetFields();setError('')}}>Начать заново</Button>}</Space>
 </Form></>}
 </Space></Card>
}
