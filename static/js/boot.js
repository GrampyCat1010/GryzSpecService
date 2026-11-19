function isMoscowNight() {
  const hour = Number(new Intl.DateTimeFormat('en-US', {timeZone:'Europe/Moscow', hour:'numeric', hour12:false}).format(new Date()));
  return hour >= 22 || hour < 6;
}
try {
  const t = localStorage.getItem('gss-theme');
  if (['light','dark','night'].includes(t)) document.documentElement.dataset.theme=isMoscowNight()?'night':t;
} catch {}
