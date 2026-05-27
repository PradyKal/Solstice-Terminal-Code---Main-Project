// Login flow via Supabase RPC verify_user
document.getElementById('login-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const u = document.getElementById('username').value.trim();
  const p = document.getElementById('password').value;
  const err = document.getElementById('login-error');
  err.textContent = '';

  const client = window.solstice.sb();
  const { data, error } = await client.rpc('verify_user', {
    p_username: u, p_password: p,
  });

  if (error) {
    err.textContent = 'ERROR: ' + error.message;
    return;
  }
  if (data && data.ok) {
    sessionStorage.setItem('solstice_user', u);
    sessionStorage.setItem('solstice_role', data.role || 'user');
    window.location.replace('terminal.html');
  } else {
    err.textContent = 'AUTHENTICATION FAILED';
  }
});
