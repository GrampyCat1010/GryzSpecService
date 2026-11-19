function isMoscowNight() {
  const hour = Number(new Intl.DateTimeFormat('en-US', {timeZone:'Europe/Moscow', hour:'numeric', hour12:false}).format(new Date()));
  return hour >= 22 || hour < 6;
}
try {
  const t = localStorage.getItem('gss-theme');
  const parts=Object.fromEntries(new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Moscow',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',hour12:false}).formatToParts(new Date()).map(p=>[p.type,p.value]));
  const hour=Number(parts.hour);
  const day=new Date(Date.UTC(Number(parts.year),Number(parts.month)-1,Number(parts.day)-(hour<6?1:0)));
  const nightKey=isMoscowNight()?day.toISOString().slice(0,10):null;
  document.documentElement.dataset.theme=nightKey&&localStorage.getItem('gss-theme-manual-night')!==nightKey?'night':['light','dark','night'].includes(t)?t:'light';
  const size=localStorage.getItem('gss-text-size');
  if(['large','larger'].includes(size))document.documentElement.dataset.textSize=size;
} catch {}
