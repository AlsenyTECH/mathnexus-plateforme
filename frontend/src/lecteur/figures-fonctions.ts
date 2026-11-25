// @ts-nocheck
/* Moteur de graphiques du parcours « Étude de fonction », repris tel quel du parcours HTML d'origine.
   Seul l'emballage change : au lieu de chercher toutes les .graph de la page au chargement,
   il expose ses figures (FIG) et la classe Graph, que le lecteur monte sur chaque étape. */

  function fr(v, d){
    if (!isFinite(v)) return v > 0 ? '+∞' : (v < 0 ? '−∞' : '?');
    var s = v.toFixed(d == null ? 3 : d).replace('.', ',');
    return s.replace('-', '−');
  }
  // t dans [-1,1] privé de 0 : x se rapproche de a quand |t| diminue (échelle logarithmique)
  function approach(a, t, span){
    var s = t < 0 ? -1 : 1, m = Math.abs(t);
    if (m < 0.02) m = 0.02;
    return a + s * span * Math.pow(10, -3.2 * (1 - m));
  }
  function sideTxt(t){ return t < 0 ? 'à gauche' : 'à droite'; }

  var FIG = {
    domaine: {
      win: function(){ return [-7, 9, -6, 8]; },
      slider: { min: -6.5, max: 8.5, step: 0.05, init: 4.5, label: 'x' },
      f: function(x){ return (x*x - 4 < 0 || x === 3) ? NaN : Math.sqrt(x*x - 4) / (x - 3); },
      draw: function(g, t){
        g.band(-7, -2, 'ok'); g.band(2, 9, 'ok'); g.band(-2, 2, 'no');
        g.vline(3, 'rouge', true);
        g.plot(this.f, 'pen');
        var y = this.f(t);
        if (isFinite(y)) g.point(t, y, 'rouge'); else g.point(t, 0, 'rouge', true);
      },
      read: function(t){
        if (Math.abs(t - 3) < 0.026) return 'x = 3 : le dénominateur x − 3 est nul, f(3) n’existe pas.';
        if (t*t - 4 < 0) return 'x = ' + fr(t, 2) + ' : x² − 4 = ' + fr(t*t - 4, 2) + ' est négatif, la racine n’existe pas.';
        return 'x = ' + fr(t, 2) + ' : f(x) existe et vaut ' + fr(this.f(t), 3) + '.';
      }
    },
    'limite-infinie': {
      win: function(){ return [-1, 7, -30, 30]; },
      slider: { min: -1, max: 1, step: 0.01, init: 0.7, label: 'approche' },
      f: function(x){ return (2*x - 1) / (x - 3); },
      draw: function(g, t){
        var x = approach(3, t, 3.5), y = this.f(x);
        g.vline(3, 'rouge', true);
        g.plot(this.f, 'pen', 3);
        g.point(x, Math.max(-30, Math.min(30, y)), 'rouge', Math.abs(y) > 30);
      },
      read: function(t){
        var x = approach(3, t, 3.5);
        return 'x = ' + fr(x, 4) + ' (' + sideTxt(t) + ' de 3) : f(x) = ' + fr(this.f(x), 1);
      }
    },
    'limite-trou': {
      win: function(){ return [-0.5, 4.5, 0, 1.5]; },
      slider: { min: -1, max: 1, step: 0.01, init: -0.8, label: 'approche' },
      f: function(x){ return x === 2 ? NaN : (x*x - x - 2) / (x*x - 4); },
      draw: function(g, t){
        var x = approach(2, t, 2.2), y = this.f(x);
        g.hline(0.75, 'prof', true);
        g.plot(this.f, 'pen');
        g.point(2, 0.75, 'pen', true);
        g.point(x, y, 'rouge');
        g.text('3/4', -0.42, 0.79, 'prof');
      },
      read: function(t){
        var x = approach(2, t, 2.2);
        return 'x = ' + fr(x, 4) + ' (' + sideTxt(t) + ' de 2) : f(x) = ' + fr(this.f(x), 4) + '   →   3/4 = 0,75';
      }
    },
    conjuguee: {
      win: function(t){ var X = Math.pow(10, t); return [0, Math.max(6, 1.25 * X), 0, 0.7]; },
      slider: { min: 0, max: 3, step: 0.01, init: 0.6, label: 'x (de 1 à 1000)' },
      f: function(x){ return x <= 0 ? NaN : Math.sqrt(x*x + x) - x; },
      draw: function(g, t){
        var x = Math.pow(10, t);
        g.hline(0.5, 'prof', true);
        g.plot(this.f, 'pen');
        g.point(x, this.f(x), 'rouge');
      },
      read: function(t){
        var x = Math.pow(10, t);
        return 'x = ' + fr(x, 1) + ' : √(x² + x) − x = ' + fr(this.f(x), 5) + '   →   1/2';
      }
    },
    sinus: {
      win: function(){ return [-7, 7, -0.4, 1.3]; },
      slider: { min: -1, max: 1, step: 0.01, init: 0.85, label: 'approche' },
      f: function(x){ return x === 0 ? NaN : Math.sin(x) / x; },
      draw: function(g, t){
        var x = approach(0, t, 6), y = this.f(x);
        g.hline(1, 'prof', true);
        g.plot(this.f, 'pen');
        g.point(0, 1, 'pen', true);
        g.point(x, y, 'rouge');
      },
      read: function(t){
        var x = approach(0, t, 6);
        return 'x = ' + fr(x, 4) + ' : sin(x)/x = ' + fr(this.f(x), 6) + '   →   1';
      }
    },
    asymptote: {
      win: function(){ return [-9, 11, -12, 16]; },
      slider: { min: -8.5, max: 10.5, step: 0.05, init: 4, label: 'x' },
      f: function(x){ return (x*x + 3) / (x - 1); },
      draw: function(g, t){
        var x = Math.abs(t - 1) < 0.3 ? (t < 1 ? 0.7 : 1.3) : t, y = this.f(x);
        g.vline(1, 'rouge', true);
        g.plot(function(u){ return u + 1; }, 'prof', null, true);
        g.plot(this.f, 'pen', 1);
        g.seg(x, x + 1, x, Math.max(-12, Math.min(16, y)), 'rouge');
        g.point(x, x + 1, 'prof');
        g.point(x, Math.max(-12, Math.min(16, y)), 'rouge', y > 16 || y < -12);
        g.text('y = x + 1', 6.2, 5.4, 'prof');
        g.text('x = 1', 1.3, -10.6, 'rouge');
      },
      read: function(t){
        var x = Math.abs(t - 1) < 0.3 ? (t < 1 ? 0.7 : 1.3) : t, e = 4 / (x - 1);
        return 'x = ' + fr(x, 2) + ' : écart f(x) − (x + 1) = ' + fr(e, 3) + (e > 0 ? '  (courbe au-dessus)' : '  (courbe au-dessous)');
      }
    },
    branche: {
      options: [
        { k: 'carre', lab: 'x²', f: function(x){ return x*x; }, verdict: 'f(x)/x → +∞ : direction (Oy)' },
        { k: 'racine', lab: '√x', f: function(x){ return x < 0 ? NaN : Math.sqrt(x); }, verdict: 'f(x)/x → 0 : direction (Ox)' },
        { k: 'mixte', lab: '2x + √x', f: function(x){ return x < 0 ? NaN : 2*x + Math.sqrt(x); }, a: 2, verdict: 'f(x)/x → 2 et f(x) − 2x → +∞ : direction y = 2x' },
        { k: 'oblique', lab: '√(4x² + x)', f: function(x){ return x < 0 ? NaN : Math.sqrt(4*x*x + x); }, a: 2, verdict: 'f(x)/x → 2 et f(x) − 2x → 1/4 : asymptote y = 2x + 1/4' }
      ],
      win: function(t, o){
        var X = Math.pow(10, t), xm = 1.2 * X, ym = 1.15 * Math.max(o.f(xm), o.f(X), 1);
        return [0, xm, 0, ym];
      },
      slider: { min: 0, max: 3, step: 0.01, init: 0.7, label: 'x (de 1 à 1000)' },
      draw: function(g, t, o){
        var x = Math.pow(10, t), y = o.f(x);
        if (o.a) g.plot(function(u){ return o.a * u; }, 'prof', null, true);
        g.plot(o.f, 'pen');
        g.seg(0, 0, x, y, 'rouge');
        g.point(x, y, 'rouge');
        g.text('M', x, y, 'rouge', -10, -10);
      },
      read: function(t, o){
        var x = Math.pow(10, t), y = o.f(x);
        var s = 'x = ' + fr(x, 1) + ' : pente de (OM) = f(x)/x = ' + fr(y / x, 4);
        if (o.a) s += '   ;   f(x) − ' + o.a + 'x = ' + fr(y - o.a * x, 4);
        return s + '\n' + o.verdict;
      }
    }
  };

  function niceStep(span){
    var raw = span / 6, p = Math.pow(10, Math.floor(Math.log10(raw))), r = raw / p;
    return (r < 1.5 ? 1 : r < 3.5 ? 2 : r < 7.5 ? 5 : 10) * p;
  }
  function tickLabel(v, step){
    var d = step >= 1 ? 0 : Math.min(4, Math.ceil(-Math.log10(step)));
    return v.toFixed(d).replace('.', ',').replace('-', '−');
  }

  function Graph(el){
    var self = this, cfg = FIG[el.dataset.fig];
    if (!cfg) return;
    this.el = el; this.cfg = cfg;
    this.opt = cfg.options ? cfg.options[0] : null;
    var html = '';
    if (cfg.options){
      html += '<div class="g-opts" role="group" aria-label="Choix de la fonction">';
      cfg.options.forEach(function(o, i){ html += '<button type="button" class="g-opt" data-i="' + i + '" aria-pressed="' + (i === 0) + '">' + o.lab + '</button>'; });
      html += '</div>';
    }
    var id = 'g-' + el.dataset.fig;
    html += '<canvas class="g-cv" role="img" aria-label="' + echapper(el.dataset.alt || 'Graphique') + '"></canvas>'
      + '<div class="g-ctl"><label for="' + id + '">' + cfg.slider.label + '</label>'
      + '<input type="range" id="' + id + '" min="' + cfg.slider.min + '" max="' + cfg.slider.max + '" step="' + cfg.slider.step + '" value="' + cfg.slider.init + '"></div>'
      + '<p class="g-read" aria-live="polite"></p>';
    el.innerHTML = html;
    this.cv = el.querySelector('canvas'); this.inp = el.querySelector('input'); this.out = el.querySelector('.g-read');
    this.inp.addEventListener('input', function(){ self.render(); });
    el.querySelectorAll('.g-opt').forEach(function(b){
      b.addEventListener('click', function(){
        self.opt = cfg.options[+b.dataset.i];
        el.querySelectorAll('.g-opt').forEach(function(c){ c.setAttribute('aria-pressed', String(c === b)); });
        self.render();
      });
    });
  }
  Graph.prototype.render = function(){
    var cv = this.cv, W = cv.clientWidth, H = cv.clientHeight;
    if (!W || !H) return;
    var dpr = window.devicePixelRatio || 1;
    if (cv.width !== Math.round(W * dpr) || cv.height !== Math.round(H * dpr)){ cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); }
    var c = cv.getContext('2d'); c.setTransform(dpr, 0, 0, dpr, 0, 0); c.clearRect(0, 0, W, H);
    var cs = getComputedStyle(document.documentElement), col = {};
    ['ink','muted','line','grid','pen','rouge','prof','surface','pen-bg','rouge-bg'].forEach(function(k){ col[k] = cs.getPropertyValue('--' + k).trim() || '#888'; });
    var t = parseFloat(this.inp.value), cfg = this.cfg, o = this.opt;
    var w = cfg.win(t, o), x0 = w[0], x1 = w[1], y0 = w[2], y1 = w[3];
    var pl = 38, pr = 10, pt = 10, pb = 22;
    function X(x){ return pl + (x - x0) / (x1 - x0) * (W - pl - pr); }
    function Y(y){ return H - pb - (y - y0) / (y1 - y0) * (H - pt - pb); }
    c.font = '12px ' + (cs.getPropertyValue('--f-body') || 'sans-serif'); c.lineJoin = 'round'; c.lineCap = 'round';

    var g = {
      band: function(a, b, kind){
        a = Math.max(a, x0); b = Math.min(b, x1); if (b <= a) return;
        c.fillStyle = kind === 'ok' ? col['pen-bg'] : col['rouge-bg'];
        c.fillRect(X(a), pt, X(b) - X(a), H - pt - pb);
      },
      vline: function(x, k, dash){ c.save(); c.strokeStyle = col[k]; c.lineWidth = 1.5; if (dash) c.setLineDash([6, 5]); c.beginPath(); c.moveTo(X(x), pt); c.lineTo(X(x), H - pb); c.stroke(); c.restore(); },
      hline: function(y, k, dash){ c.save(); c.strokeStyle = col[k]; c.lineWidth = 1.5; if (dash) c.setLineDash([6, 5]); c.beginPath(); c.moveTo(pl, Y(y)); c.lineTo(W - pr, Y(y)); c.stroke(); c.restore(); },
      seg: function(xa, ya, xb, yb, k){ c.save(); c.strokeStyle = col[k]; c.lineWidth = 2; c.beginPath(); c.moveTo(X(xa), Y(ya)); c.lineTo(X(xb), Y(yb)); c.stroke(); c.restore(); },
      plot: function(f, k, pole, dash){
        c.save(); c.beginPath(); c.rect(pl, pt, W - pl - pr, H - pt - pb); c.clip();
        c.strokeStyle = col[k]; c.lineWidth = dash ? 1.6 : 2.4; if (dash) c.setLineDash([7, 5]);
        var n = Math.max(200, Math.round(W * 1.5)), pen = false, py = 0, px = 0; c.beginPath();
        for (var i = 0; i <= n; i++){
          var x = x0 + (x1 - x0) * i / n, y = f(x);
          var jump = pen && (Math.abs(Y(y) - py) > H * 1.2 || (pole != null && (px - pole) * (x - pole) <= 0));
          if (!isFinite(y) || jump){ pen = false; if (!isFinite(y)) { px = x; continue; } }
          var yy = Math.max(-4 * H, Math.min(5 * H, Y(y)));
          if (pen) c.lineTo(X(x), yy); else { c.moveTo(X(x), yy); pen = true; }
          py = yy; px = x;
        }
        c.stroke(); c.restore();
      },
      point: function(x, y, k, open){
        c.save(); c.beginPath(); c.arc(X(x), Y(y), 5, 0, 6.2832);
        c.fillStyle = open ? col.surface : col[k]; c.fill(); c.lineWidth = 2; c.strokeStyle = col[k]; c.stroke(); c.restore();
      },
      text: function(s, x, y, k, dx, dy){ c.save(); c.fillStyle = col[k]; c.font = '600 13px ' + (cs.getPropertyValue('--f-body') || 'sans-serif'); c.textAlign = dx ? 'right' : 'left'; c.fillText(s, X(x) + (dx || 0), Y(y) + (dy || 0)); c.restore(); }
    };

    // fond, quadrillage, axes
    c.fillStyle = col.surface; c.fillRect(0, 0, W, H);
    var sx = niceStep(x1 - x0), sy = niceStep(y1 - y0), v;
    c.strokeStyle = col.grid; c.lineWidth = 1; c.fillStyle = col.muted;
    c.textAlign = 'center'; c.textBaseline = 'top';
    for (v = Math.ceil(x0 / sx) * sx; v <= x1 + 1e-9; v += sx){
      c.beginPath(); c.moveTo(X(v), pt); c.lineTo(X(v), H - pb); c.stroke();
      c.fillText(tickLabel(Math.abs(v) < 1e-9 ? 0 : v, sx), X(v), H - pb + 5);
    }
    c.textAlign = 'right'; c.textBaseline = 'middle';
    for (v = Math.ceil(y0 / sy) * sy; v <= y1 + 1e-9; v += sy){
      c.beginPath(); c.moveTo(pl, Y(v)); c.lineTo(W - pr, Y(v)); c.stroke();
      c.fillText(tickLabel(Math.abs(v) < 1e-9 ? 0 : v, sy), pl - 5, Y(v));
    }
    c.textBaseline = 'alphabetic';
    c.strokeStyle = col.muted; c.lineWidth = 1.4;
    if (y0 <= 0 && y1 >= 0){ c.beginPath(); c.moveTo(pl, Y(0)); c.lineTo(W - pr, Y(0)); c.stroke(); }
    if (x0 <= 0 && x1 >= 0){ c.beginPath(); c.moveTo(X(0), pt); c.lineTo(X(0), H - pb); c.stroke(); }

    cfg.draw(g, t, o);
    this.out.textContent = cfg.read(t, o);
  };


// Correctif de sécurité : data-alt vient du contenu ; il est échappé avant d'entrer dans innerHTML.
function echapper(texte) {
  return String(texte).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c])
}

export { FIG, Graph }
