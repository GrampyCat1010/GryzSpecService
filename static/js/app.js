import {api} from './api.js';
import {initNavigation} from './navigation.js';
import {initTheme} from './theme.js';
import {fillContacts,initDialogs,toast,el,safeURL} from './ui.js';
import {initForms} from './forms.js';
import {initChat} from './chatbot.js';
initNavigation();initTheme();initDialogs();initChat();
async function start(){
  try{const [config,services]=await Promise.all([api('config'),api('services')]);fillContacts(config);initForms(config,services);}catch(e){toast(e.message);const picker=document.querySelector('#service-picker');const note=el('p','form-error','Не удалось загрузить форму.');const retry=el('button','text-link','Повторить загрузку');retry.addEventListener('click',()=>{picker.replaceChildren();start();});picker.append(note,retry);document.querySelectorAll('.submit-button').forEach(b=>b.disabled=true);return;}
  document.querySelectorAll('.submit-button').forEach(b=>b.disabled=false);
}
start();
api('reviews').then(data=>{if(!safeURL(data.widget_url))return;const box=document.querySelector('#reviews-content'),iframe=el('iframe');iframe.src=data.widget_url;iframe.title='Отзывы о ГрузСпецСервис на Яндекс Картах';iframe.loading='lazy';iframe.referrerPolicy='strict-origin-when-cross-origin';box.replaceChildren(iframe);if(safeURL(data.url)){const a=el('a','text-link','Все отзывы на Яндекс Картах ↗');a.href=data.url;a.target='_blank';a.rel='noopener';box.append(a);}}).catch(()=>{});
api('stats').then(data=>{const box=document.querySelector('#real-stats'),parts=[];if(data.completed_orders>0)parts.push(`Завершённых заявок с сайта: ${data.completed_orders.toLocaleString('ru-RU')}`);if(data.years>0)parts.push(`${data.years} лет работы`);if(parts.length){box.textContent=parts.join(' · ');box.hidden=false;}}).catch(()=>{});
