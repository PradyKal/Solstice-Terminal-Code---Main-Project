// Hash-based router for terminal tabs
window.solstice.router = {
  routes: ['analyze','portfolio','trades','models','simulations','risk','regime','attribution','engine','logs'],
  init() {
    const apply = () => {
      let target = (location.hash || '#analyze').replace('#','');
      if (!this.routes.includes(target)) target = 'analyze';
      document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
      document.getElementById('view-' + target)?.classList.add('active');
      document.querySelectorAll('.sidebar .tab').forEach(t => {
        t.classList.toggle('active', t.getAttribute('href') === '#' + target);
      });
      const handler = window.solstice.tabs?.[target];
      if (handler && !handler._initialized) {
        handler.mount();
        handler._initialized = true;
      } else if (handler?.focus) {
        handler.focus();
      }
    };
    window.addEventListener('hashchange', apply);
    apply();
  },
};
