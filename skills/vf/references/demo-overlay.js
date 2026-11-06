// Demo overlay: draws a demo's caption, the badge naming whose screen is showing, and the full-screen switch card
// into the page being recorded. Copy it into the harness's demos/ folder unchanged, and install it in every page the
// demo records before the page's own scripts run (Playwright: context.add_init_script(path=...)). It reads what to
// draw from sessionStorage, so it survives page loads and re-renders, and it ignores pointer events, so it never
// changes what the page does. A demo sets one of three keys, then calls window.__demoDraw():
//
//   demoCaption  the caption text, or removed for none
//   demoScreen   JSON {"badge": "Customer view: Checkout", "color": "#047857"}, or removed for none
//   demoCard     JSON {"title": "Customer side", "detail": "A shopper pays for an order", "color": "#047857"},
//                shown full screen over the page, or removed
//
// sessionStorage belongs to one origin and one tab, so a demo that moves to another origin sets the keys again
// after the page loads. Pick colors that keep white text readable, one per person, the same on the badge and card.
(() => {
  const font = '-apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", Arial, sans-serif';
  const ensure = (id, style) => {
    let el = document.getElementById(id);
    if (!el) {
      el = document.createElement('div');
      el.id = id;
      Object.assign(el.style, {position: 'fixed', zIndex: '2147483647', pointerEvents: 'none'}, style);
      document.body.appendChild(el);
    }
    return el;
  };
  const drop = (id) => { const el = document.getElementById(id); if (el) el.remove(); };
  const read = (key) => { try { return JSON.parse(sessionStorage.getItem(key) || 'null'); } catch (e) { return null; } };
  const draw = () => {
    if (!document.body) return;
    const caption = sessionStorage.getItem('demoCaption') || '';
    const screen = read('demoScreen');
    const card = read('demoCard');
    if (caption) {
      // Above the bottom edge, where apps often keep an input bar.
      const el = ensure('demo-caption', {
        left: '50%', bottom: '18%', transform: 'translateX(-50%)', maxWidth: '60%', textAlign: 'center',
        background: 'rgba(20, 20, 24, 0.92)', color: '#ffffff', padding: '14px 28px', borderRadius: '12px',
        boxShadow: '0 8px 28px rgba(0, 0, 0, 0.35)', font: '600 25px/1.35 ' + font,
      });
      if (el.textContent !== caption) el.textContent = caption;
    } else drop('demo-caption');
    if (screen) {
      const el = ensure('demo-screen', {
        left: '50%', top: '10px', transform: 'translateX(-50%)', color: '#ffffff', padding: '9px 18px',
        borderRadius: '999px', font: '700 19px/1.2 ' + font, boxShadow: '0 6px 20px rgba(0, 0, 0, 0.3)',
      });
      el.style.background = screen.color || '#334155';
      if (el.textContent !== screen.badge) el.textContent = screen.badge || '';
    } else drop('demo-screen');
    if (card) {
      const el = ensure('demo-card', {
        inset: '0', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        gap: '18px', color: '#ffffff', textAlign: 'center', font: '700 64px/1.15 ' + font,
      });
      el.style.background = card.color || '#334155';
      const key = JSON.stringify(card);
      if (el.dataset.key !== key) {
        el.replaceChildren();
        const title = document.createElement('div');
        title.textContent = card.title || '';
        const detail = document.createElement('div');
        Object.assign(detail.style, {fontWeight: '500', fontSize: '32px', opacity: '0.92'});
        detail.textContent = card.detail || '';
        el.append(title, detail);
        el.dataset.key = key;
      }
    } else drop('demo-card');
  };
  window.__demoDraw = draw;
  setInterval(draw, 200);
  document.addEventListener('DOMContentLoaded', draw);
})();
