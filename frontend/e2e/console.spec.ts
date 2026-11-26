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
