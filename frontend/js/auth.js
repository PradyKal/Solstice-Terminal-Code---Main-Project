const bootSteps = [
  'init secure crypto module',
  'establish supabase tls',
  'verify bcrypt handler',
  'load auth schema',
  '› ready for authentication',
];
const bootEl = document.getElementById('boot');
bootSteps.forEach((s, i) => setTimeout(() => {
  const div = document.createElement('div');
  div.className = 'step' + (s.startsWith('›') ? ' ok' : '');
  div.textContent = s;
  bootEl.appendChild(div);
}, i * 180));

document.getElementById('login-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const u = document.getElementById('username').value.trim();
  const p = document.getElementById('password').value;
  const err = document.getElementById('login-error');
  err.style.color = '#f59e0b';
  err.textContent = '› authenticating…';

  try {
    const { data, error } = await window.solstice.sb().rpc('verify_user', { p_username: u, p_password: p });
    if (error) { err.style.color = '#ef4444'; err.textContent = '✗ ' + error.message; return; }
    if (!data?.ok) { err.style.color = '#ef4444'; err.textContent = '✗ ' + (data?.reason || 'failed'); return; }
    sessionStorage.setItem('solstice_user', u);
    sessionStorage.setItem('solstice_role', data.role || 'user');
    err.style.color = '#10b981';
    err.textContent = '✓ authenticated · entering terminal';
    setTimeout(() => {
      try { window.top.location.href = 'research.html'; } catch(_) {}
      window.location.assign('research.html');
    }, 350);
  } catch (ex) {
    err.style.color = '#ef4444';
    err.textContent = '✗ ' + ex.message;
  }
});
