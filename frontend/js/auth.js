// Login flow with cinematic boot sequence + Supabase RPC verify
const bootSteps = [
  'init crypto module',
  'connect supabase rpc',
  'verify bcrypt handler',
  'establish secure channel',
  'load auth schema',
  '› ready for authentication',
];
const bootEl = document.getElementById('boot');
let _bootRun = false;
function runBoot() {
  if (_bootRun) return;
  _bootRun = true;
  bootEl.innerHTML = '';
  bootSteps.forEach((s, i) => {
    setTimeout(() => {
      const div = document.createElement('div');
      div.className = 'step' + (s.startsWith('›') ? ' ok' : '');
      div.textContent = s;
      bootEl.appendChild(div);
    }, i * 200);
  });
}
runBoot();

document.getElementById('login-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const u = document.getElementById('username').value.trim();
  const p = document.getElementById('password').value;
  const err = document.getElementById('login-error');
  err.style.color = '#f59e0b';
  err.textContent = '› authenticating…';

  try {
    const client = window.solstice.sb();
    const { data, error } = await client.rpc('verify_user', {
      p_username: u, p_password: p,
    });

    if (error) {
      err.style.color = '#ef4444';
      err.textContent = '✗ RPC error: ' + (error.message || JSON.stringify(error));
      console.error('verify_user error:', error);
      return;
    }
    if (!data) {
      err.style.color = '#f59e0b';
      err.textContent = '✗ no response from server';
      return;
    }
    if (data.ok === true) {
      sessionStorage.setItem('solstice_user', u);
      sessionStorage.setItem('solstice_role', data.role || 'user');
      err.style.color = '#10b981';
      err.textContent = '✓ authenticated · entering terminal';
      setTimeout(() => {
        try { window.top.location.href = 'terminal.html'; } catch(_) {}
        try { window.parent.location.href = 'terminal.html'; } catch(_) {}
        window.location.assign('terminal.html');
        window.location.href = 'terminal.html';
      }, 350);
    } else {
      err.style.color = '#ef4444';
      err.textContent = '✗ AUTH FAILED · ' + (data.reason || 'unknown');
    }
  } catch (ex) {
    err.style.color = '#ef4444';
    err.textContent = '✗ fatal: ' + ex.message;
    console.error(ex);
  }
});
