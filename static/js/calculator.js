import {api} from './api.js';
import {money} from './ui.js';
export function initCalculator(form,getData,services){
  const mobile=matchMedia('(max-width:760px)'),disclosure=document.querySelector('.estimate-disclosure');disclosure.open=!mobile.matches;mobile.addEventListener('change',()=>disclosure.open=!mobile.matches);
  let timer,revision=0;
  const visitInput = form.querySelector('[name="visit"], #visit');
  const urgentInput = form.querySelector('[name="urgent"], #urgent');
  const urgentBox = urgentInput?.closest('label, .field, .checkbox, .form-field') || urgentInput;

  function syncUrgentVisibility() {
    const show = !!visitInput?.checked;
    if (urgentBox) urgentBox.hidden = !show;
    if (!show && urgentInput?.checked) {
      urgentInput.checked = false;
      urgentInput.dispatchEvent(new Event('change', { bubbles: true }));
    }
  }

  visitInput?.addEventListener('change', syncUrgentVisibility);
  document.addEventListener('gss:calculation', syncUrgentVisibility);
  syncUrgentVisibility();
  async function update(){const mine=++revision,data=getData();document.querySelector('#estimate-service').textContent=services.find(s=>s.id===data.service)?.title||'';try{const result=await api('calculator',{method:'POST',body:data});if(mine!==revision)return;document.querySelector('#estimate-total').textContent=result.individual?'Индивидуально':'от '+money(result.total_from);document.querySelector('#estimate-work').textContent=result.work_from===null?'По запросу':'от '+money(result.work_from);document.querySelector('#estimate-travel').textContent=data.visit?'от '+money(result.visit_from):'Не нужен';const types={road:'по дороге',approximate:'оценка'};document.querySelector('#estimate-distance').textContent=result.distance_km===null?(data.visit?'Уточним маршрут':'—'):`${result.distance_km.toLocaleString('ru-RU')} км · ${types[result.distance_source]}`;document.querySelector('#estimate-note').textContent=(result.distance_pending?'Стоимость выезда предварительная: расстояние ещё не учтено. ':result.distance_source==='approximate'?'Расстояние оценено по прямой с поправкой на дорогу. ':'')+result.note;}catch(e){if(mine===revision){document.querySelector('#estimate-total').textContent='Уточним стоимость';document.querySelector('#estimate-note').textContent=e.message;}}}
  const compact=document.querySelector('#estimate-compact');new MutationObserver(()=>compact.textContent=document.querySelector('#estimate-total').textContent).observe(document.querySelector('#estimate-total'),{childList:true});
   function schedule(){clearTimeout(timer);timer=setTimeout(update,350);}
  function immediate(){clearTimeout(timer);update();}
  form.addEventListener('input',schedule);form.addEventListener('change',immediate);document.addEventListener('gss:calculation',immediate);update();
}
