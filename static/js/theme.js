export function initTheme(){
  const buttons=document.querySelectorAll('[data-theme-choice]');
  const stored=()=>{try{const theme=localStorage.getItem('gss-theme');return ['light','dark','night'].includes(theme)?theme:'light';}catch{return 'light';}};
  const moscowNight=()=>{const hour=Number(new Intl.DateTimeFormat('en-US',{timeZone:'Europe/Moscow',hour:'numeric',hour12:false}).format(new Date()));return hour>=22||hour<6;};
  function apply(){const selected=stored(),theme=moscowNight()?'night':selected;document.documentElement.dataset.theme=theme;buttons.forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.themeChoice===theme)));document.querySelector('meta[name="theme-color"]').content=theme==='light'?'#f5f5f2':theme==='dark'?'#242624':'#0c100d';}
  buttons.forEach(b=>b.addEventListener('click',()=>{try{localStorage.setItem('gss-theme',b.dataset.themeChoice);}catch{}apply();}));
  apply();
  window.setInterval(apply,30000);
}
