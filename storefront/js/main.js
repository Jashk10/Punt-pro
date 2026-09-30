document.documentElement.classList.add('js');

/* Mobile nav */
const menuBtn = document.querySelector('.menu-btn');
const nav = document.getElementById('primary-nav');
menuBtn.addEventListener('click', () => {
  const open = nav.classList.toggle('is-open');
  menuBtn.setAttribute('aria-expanded', String(open));
});
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && nav.classList.contains('is-open')) {
    nav.classList.remove('is-open');
    menuBtn.setAttribute('aria-expanded', 'false');
    menuBtn.focus();
  }
});

/* Wishlist — persists in localStorage when available */
const KEY = 'cc-wishlist';
const read = () => { try { return JSON.parse(localStorage.getItem(KEY)) || []; } catch { return []; } };
const write = (list) => { try { localStorage.setItem(KEY, JSON.stringify(list)); } catch { /* storage unavailable */ } };
const countEl = document.getElementById('wish-count');
let saved = read();

function paintWishlist() {
  countEl.textContent = saved.length;
  countEl.hidden = saved.length === 0;
  document.querySelectorAll('.wish').forEach((btn) => {
    const on = saved.includes(btn.dataset.id);
    btn.setAttribute('aria-pressed', String(on));
    btn.setAttribute('aria-label', `${on ? 'Remove from' : 'Save to'} wishlist: ${btn.dataset.name}`);
  });
}
document.querySelectorAll('.wish').forEach((btn) => {
  btn.addEventListener('click', () => {
    saved = saved.includes(btn.dataset.id) ? saved.filter((id) => id !== btn.dataset.id) : [...saved, btn.dataset.id];
    write(saved);
    paintWishlist();
  });
});
paintWishlist();

/* Email capture — no backend wired yet */
const form = document.getElementById('signup');
const email = document.getElementById('email');
const msg = document.getElementById('signup-msg');
form.addEventListener('submit', (e) => {
  e.preventDefault();
  const ok = email.validity.valid && email.value.trim() !== '';
  email.setAttribute('aria-invalid', String(!ok));
  msg.classList.toggle('hint--error', !ok);
  msg.textContent = ok
    ? 'Thank you. Your first letter will arrive with the next loom update.'
    : 'Please enter an email address, like name@example.com.';
  if (!ok) email.focus();
  else form.reset();
});

/* Fade-ins */
const items = document.querySelectorAll('.reveal');
if ('IntersectionObserver' in window) {
  const io = new IntersectionObserver((entries) => {
    entries.forEach((en) => { if (en.isIntersecting) { en.target.classList.add('is-in'); io.unobserve(en.target); } });
  }, { threshold: 0.12 });
  items.forEach((el) => io.observe(el));
} else {
  items.forEach((el) => el.classList.add('is-in'));
}
