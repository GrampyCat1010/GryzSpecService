export function initTheme(){
  const buttons=document.querySelectorAll('[data-theme-choice]');
  function set(theme){document.documentElement.dataset.theme=theme;buttons.forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.themeChoice===theme)));try{localStorage.setItem('gss-theme',theme);}catch{}document.querySelector('meta[name="theme-color"]').content=theme==='light'?'#f5f5f2':theme==='dark'?'#242624':'#0c100d';}
  buttons.forEach(b=>b.addEventListener('click',()=>set(b.dataset.themeChoice)));set(document.documentElement.dataset.theme||'light');
}
