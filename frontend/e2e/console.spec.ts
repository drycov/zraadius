import {test,expect} from '@playwright/test';
test('login, navigation and NAS creation with numeric/string payload preservation',async({page})=>{
 let created:unknown;
 await page.route('**/api/v1/**',async route=>{const path=new URL(route.request().url()).pathname;
 if(path.endsWith('/iam/login'))return route.fulfill({json:{access_token:'test-session',username:'admin',role:'admin'}});
 if(path.endsWith('/dashboard'))return route.fulfill({json:{users:1,nas:0,groups:0,disabled_users:0,open_sessions:0,accounting_records:0,audit_24h:0}});
 if(path.endsWith('/nas')&&route.request().method()==='POST'){created=route.request().postDataJSON();return route.fulfill({status:201,json:{id:1}})}
 return route.fulfill({json:[]})});
 await page.goto('/');await page.getByLabel('Логин').fill('admin');await page.getByLabel('Пароль').fill('test-password');await page.getByRole('button',{name:'Войти'}).click();
 await expect(page.getByRole('heading',{name:'Dashboard'})).toBeVisible();
 await page.getByRole('button',{name:'NAS',exact:true}).click();await expect(page).toHaveURL(/#\/nas$/);
 await page.getByLabel('IP',{exact:true}).fill('192.0.2.10');await page.getByLabel('Имя',{exact:true}).fill('BNG-01');await page.getByLabel('Shared Secret').fill('a'.repeat(32));await page.getByRole('button',{name:'Добавить',exact:true}).click();
 await expect.poll(()=>created).toMatchObject({address:'192.0.2.10',name:'BNG-01',vendor:'mikrotik'});
 await page.goBack();await expect(page.getByRole('heading',{name:'Dashboard'})).toBeVisible();
});

test('accounting exact filter and cursor navigation',async({page})=>{
 const calls:string[]=[];
 await page.route('**/api/v1/**',async route=>{
  const u=new URL(route.request().url());
  if(u.pathname.endsWith('/iam/login'))return route.fulfill({json:{access_token:'test',username:'admin',role:'admin'}});
  if(u.pathname.endsWith('/accounting')){calls.push(u.search);const start=u.searchParams.has('before')?100:201;return route.fulfill({json:Array.from({length:u.searchParams.has('before')?1:101},(_,i)=>({radacctid:start-i,username:'test-user',nasipaddress:'192.0.2.1',acctstoptime:'2026-01-01'}))})}
  return route.fulfill({json:[]})
 });
 await page.goto('/#/accounting');await page.getByLabel('Логин').fill('admin');await page.getByLabel('Пароль').fill('test-password');await page.getByRole('button',{name:'Войти'}).click();
 await page.getByLabel('Username',{exact:true}).fill('test-user');await page.getByRole('button',{name:'Применить'}).click();
 await expect.poll(()=>calls.some(s=>s.includes('username=test-user'))).toBeTruthy();
 await page.getByRole('button',{name:'Далее',exact:true}).click();
 await expect.poll(()=>calls.some(s=>s.includes('before=102')&&s.includes('username=test-user'))).toBeTruthy();
});

test('subscriber groups expand inline, load on demand and filter',async({page})=>{
 const calls:string[]=[];
 await page.route('**/api/v1/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  calls.push(path);
  if(path.endsWith('/iam/login'))return route.fulfill({json:{access_token:'test-session',username:'admin',role:'admin'}});
  if(path.endsWith('/groups'))return route.fulfill({json:[{name:'INTERNET-100M'},{name:'INTERNET-500M'}]});
  if(path.endsWith('/profile'))return route.fulfill({json:[{attribute:'Mikrotik-Rate-Limit',op:':=',value:'100M/100M'}]});
  return route.fulfill({json:[]});
 });
 await page.goto('/#/groups');await page.getByLabel('Логин').fill('admin');await page.getByLabel('Пароль').fill('test-password');await page.getByRole('button',{name:'Войти'}).click();
 const first=page.getByRole('button',{name:'INTERNET-100M',exact:true});
 const second=page.getByRole('button',{name:'INTERNET-500M',exact:true});
 await expect(first).toHaveAttribute('aria-expanded','false');
 expect(calls.some(x=>x.endsWith('/profile'))).toBeFalsy();
 await first.click();await expect(first).toHaveAttribute('aria-expanded','true');await expect(page.getByText('100M/100M',{exact:true})).toBeVisible();
 await second.click();await expect(first).toHaveAttribute('aria-expanded','false');await expect(second).toHaveAttribute('aria-expanded','true');
 await second.click();await expect(second).toHaveAttribute('aria-expanded','false');
 await page.getByRole('searchbox',{name:'Поиск групп'}).fill('500M');await expect(first).toHaveCount(0);await expect(second).toBeVisible();
});
