/* Front-end preview session. Replace with the app's server-backed auth provider when available. */
(() => {
  const KEY = 'fc_preview_user';
  const parse = () => { try { return JSON.parse(sessionStorage.getItem(KEY) || 'null'); } catch { return null; } };
  window.FCAuth = {
    currentUser: parse,
    signIn(user) { sessionStorage.setItem(KEY, JSON.stringify(user)); },
    signOut() { sessionStorage.removeItem(KEY); },
    requireUser() { const user = parse(); if (!user) location.replace('login.html?next=home.html'); return user; }
  };
  const form = document.querySelector('#signin-form');
  if (form) {
    const params = new URLSearchParams(location.search);
    const pending = (() => { try { return JSON.parse(sessionStorage.getItem('fc_pending_registration') || 'null'); } catch { return null; } })();
    if (pending) { form.elements.name.value = pending.name || ''; form.elements.email.value = pending.email || ''; }
    if (params.has('email')) form.elements.email.value = params.get('email');
    if (params.has('name')) form.elements.name.value = params.get('name');
    form.addEventListener('submit', event => {
      event.preventDefault();
      const data = new FormData(form);
      const email = String(data.get('email')).trim();
      const name = String(data.get('name')).trim() || email.split('@')[0];
      const role = pending?.role || 'freelancer';
      window.FCAuth.signIn({ name, email, role });
      sessionStorage.removeItem('fc_pending_registration');
      location.href = 'home.html';
    });
  }
  document.querySelectorAll('.form-card form').forEach(registrationForm => registrationForm.addEventListener('submit', event => {
    event.preventDefault();
    const values = new FormData(registrationForm);
    const role = location.pathname.includes('recruter') ? 'recruiter' : 'freelancer';
    sessionStorage.setItem('fc_pending_registration', JSON.stringify({name:String(values.get('name')).trim(), email:String(values.get('email')).trim(), role}));
    location.href = 'login.html';
  }));
})();
