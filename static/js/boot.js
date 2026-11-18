try { const t = localStorage.getItem('gss-theme'); if (['light','dark','night'].includes(t)) document.documentElement.dataset.theme=t; } catch {}
