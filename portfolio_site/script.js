// SeeFire portfolio — scroll reveals + click/tap-to-play films.

// Staggered reveal on scroll.
const io = new IntersectionObserver((entries) => {
  for (const e of entries) {
    if (e.isIntersecting) {
      e.target.classList.add('in');
      io.unobserve(e.target);
    }
  }
}, { threshold: 0.12, rootMargin: '0px 0px -8% 0px' });

document.querySelectorAll('.reveal').forEach((el) => io.observe(el));

// Films: explicit play/pause. Tap (touch) or click the button to play;
// hover-capable devices also preview on hover. Nothing autoplays.
const canHover = window.matchMedia('(hover: hover)').matches;

document.querySelectorAll('.film').forEach((fig) => {
  const v = fig.querySelector('video');
  if (!v) return;

  // Inject play overlay.
  const btn = document.createElement('button');
  btn.className = 'film__play';
  btn.type = 'button';
  btn.setAttribute('aria-label', 'Play video');
  btn.innerHTML = '<span class="ico" aria-hidden="true"></span>';
  fig.appendChild(btn);

  const play  = () => v.play().catch(() => {});
  const pause = () => v.pause();
  const toggle = () => (v.paused ? play() : pause());

  v.addEventListener('play',  () => fig.classList.add('playing'));
  v.addEventListener('pause', () => fig.classList.remove('playing'));
  v.addEventListener('ended', () => fig.classList.remove('playing'));

  btn.addEventListener('click', (e) => { e.preventDefault(); play(); });
  v.addEventListener('click', toggle);

  if (canHover) {
    fig.addEventListener('mouseenter', play);
    fig.addEventListener('mouseleave', pause);
  }
});
