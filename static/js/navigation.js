const views=['home','settings','personal','corporate','services'];
export function navigate(view,{replace=false,focus=true,targetId}={}) {
  if(!views.includes(view))view='home';
  document.querySelectorAll('[data-page]').forEach(page=>page.hidden=page.dataset.page!==view);
  document.querySelectorAll('.navigation [data-view]').forEach(button=>{if(button.dataset.view===view)button.setAttribute('aria-current','page');else button.removeAttribute('aria-current');});
  const url=new URL(location.href);if(view==='home')url.searchParams.delete('view');else url.searchParams.set('view',view);
  if(url.href!==location.href)history[replace?'replaceState':'pushState']({view},'',url);
  const target=targetId&&document.getElementById(targetId);
  if(target){
    target.scrollIntoView({block:'start',behavior:'instant'});
    if(focus)target.focus({preventScroll:true});
  }else{
    window.scrollTo({top:0,behavior:'instant'});
    if(focus)document.querySelector('#main').focus({preventScroll:true});
  }
  document.dispatchEvent(new CustomEvent('gss:view',{detail:view}));
}
export function initNavigation(){
  document.querySelectorAll('[data-view]').forEach(button=>button.addEventListener('click',()=>navigate(button.dataset.view,{targetId:button.dataset.viewTarget})));
  window.addEventListener('popstate',()=>navigate(new URLSearchParams(location.search).get('view')||'home',{replace:true}));
  navigate(new URLSearchParams(location.search).get('view')||'home',{replace:true,focus:false});
}
