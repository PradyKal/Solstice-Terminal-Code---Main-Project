// Login flow via Supabase RPC verify_user — with visible diagnostics
document.getElementById('login-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const u = document.getElementById('username').value.trim();
  const p = document.getElementById('password').value;
  const err = document.getElementById('login-error');
  err.style.color = '';
  err.textContent = 'authenticating...';

  try {
    const client = window.solstice.sb();
    const { data, error } = await client.rpc('verify_user', {
      p_username: u, p_password: p,
    });

    if (error) {
      err.style.color = '#f43f5e';
      err.textContent = 'RPC error: ' + (error.message || JSON.stringify(error));
      console.error('verify_user error:', error);
      return;
    }
    if (!data) {
      err.style.color = '#fbbf24';
      err.textContent = 'no response from server';
      return;
    }
    if (data.ok === true) {
      sessionStorage.setItem('solstice_user', u);
      sessionStorage.setItem('solstice_role', data.role || 'user');
      err.style.color = '#4ade80';
      err.textContent = 'OK · entering terminal';
      // Triple-redundant redirect (handles sandboxed iframes)
      setTimeout(() => {
        try { window.top.location.href = 'terminal.html'; } catch(_) {}
        try { window.parent.location.href = 'terminal.html'; } catch(_) {}
        window.location.assign('terminal.html');
        window.location.href = 'terminal.html';
      }, 150);
    } else {
      err.style.color = '#f43f5e';
      err.textContent = 'AUTH FAILED · ' + (data.reason || 'unknown');
    }
  } catch (ex) {
    err.style.color = '#f43f5e';
    err.textContent = 'fatal: ' + ex.message;
    console.error(ex);
  }
});
