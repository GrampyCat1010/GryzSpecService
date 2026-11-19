import {api} from './api.js';
export function icon(name) { const svg=document.createElementNS('http://www.w3.org/2000/svg','svg'); const use=document.createElementNS(svg.namespaceURI,'use'); use.setAttribute('href','#i-'+name); svg.setAttribute('aria-hidden','true');svg.append(use);return svg; }
export function el(tag,className,text) { const node=document.createElement(tag);if(className)node.className=className;if(text!==undefined)node.textContent=text;return node; }
let toastTimer;
export function toast(message) {const node=document.querySelector('.toast');node.textContent=message;node.hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>node.hidden=true,6000);}
export const money=value=>value===null?'По запросу':new Intl.NumberFormat('ru-RU').format(value)+' ₽';
export function safeURL(value) {try {const url=new URL(value);return url.protocol==='https:'?url.href:null;}catch{return null;}}
export function initDialogs(){
  const cookieInfo=el('section','settings-section settings-privacy');const copy=el('div');copy.append(el('h2','','Cookies и локальные настройки'),el('p','muted','В браузере хранится только выбранная тема. Рекламных и аналитических cookies нет. При загрузке карт и отзывов действуют правила Яндекса'));cookieInfo.append(copy);document.querySelector('.settings-grid').append(cookieInfo);
  document.querySelectorAll('[data-close-dialog]').forEach(button=>button.addEventListener('click',()=>button.closest('dialog').close()));
  document.querySelectorAll('.content-dialog').forEach(dialog=>dialog.addEventListener('click',event=>{if(event.target===dialog){const r=dialog.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)dialog.close();}}));
  document.querySelectorAll('[data-privacy]').forEach(button=>button.addEventListener('click',async()=>{const dialog=document.querySelector('#privacy-dialog'),text=document.querySelector('#privacy-text');text.textContent='Загружаем документ…';dialog.showModal();try{text.textContent=(await api('privacy')).text;}catch(e){text.textContent=e.message;}}));
  let scrollY=0;
  const syncPageScroll=()=>{
    const hasOpenDialog=Boolean(document.querySelector('dialog[open]'));
    if(hasOpenDialog&&!document.body.classList.contains('dialog-open')){
      scrollY=window.scrollY;
      document.body.style.top=`-${scrollY}px`;
      document.body.classList.add('dialog-open');
    }else if(!hasOpenDialog&&document.body.classList.contains('dialog-open')){
      document.body.classList.remove('dialog-open');
      document.body.style.top='';
      window.scrollTo(0,scrollY);
    }
  };
  document.querySelectorAll('dialog').forEach(dialog=>{new MutationObserver(syncPageScroll).observe(dialog,{attributes:true,attributeFilter:['open']});});
}
export function fillContacts(config){
  document.querySelector('#year').textContent=new Date().getFullYear();
  document.querySelectorAll('[data-phone]').forEach(a=>{a.textContent=config.phone||'+7 (___) ___-__-__';const number=config.phone.replace(/[^+\d]/g,'');if(/^\+?\d{10,15}$/.test(number))a.href='tel:'+number;});
  document.querySelectorAll('[data-contact="address"]').forEach(e=>e.textContent=config.address||'Адрес сервиса уточняется');
  document.querySelectorAll('[data-email]').forEach(a=>{if(config.email){a.textContent=config.email;a.href='mailto:'+config.email;a.hidden=false;}});
  const years=Number(config.years);const yearsBox=document.querySelector('[data-years]');
  if(yearsBox&&years>0){const label=years%10===1&&years%100!==11?'год':years%10>=2&&years%10<=4&&(years%100<10||years%100>=20)?'года':'лет';yearsBox.textContent=`${years} ${label} работы`;yearsBox.hidden=false;}
  for(const channel of ['telegram','max']) {const block=document.querySelector(`[data-messenger="${channel}"]`),url=safeURL(config[channel+'_url']);if(url){const img=block.querySelector('img'),a=block.querySelector('a'),footerLink=document.querySelector(`[data-footer-messenger="${channel}"]`);img.src='/api/qr/'+channel;img.hidden=false;a.href=url;a.hidden=false;block.querySelector('small').hidden=true;if(footerLink){footerLink.href=url;footerLink.hidden=false;}}}
}
