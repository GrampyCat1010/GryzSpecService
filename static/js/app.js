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
api('reviews').then(data=>{if(!safeURL(data.widget_url))return;const box=document.querySelector('#reviews-content'),iframe=el('iframe');iframe.src=data.widget_url;iframe.title='Отзывы о ГрузСпецСервис на Яндекс Картах';iframe.loading='lazy';iframe.referrerPolicy='strict-origin-when-cross-origin';box.replaceChildren(iframe);}).catch(()=>{});
