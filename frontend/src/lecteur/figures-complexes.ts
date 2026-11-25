// @ts-nocheck
/* Moteur de graphiques du parcours « Nombres complexes », repris tel quel du parcours HTML d'origine.
   Seul l'emballage change : au lieu de chercher toutes les .graph de la page au chargement,
   il expose ses figures (FIG) et la classe Graph, que le lecteur monte sur chaque étape. */

  function fr(v, d){
    if (Math.abs(v) < 1e-9) v = 0;
    var s = (+v.toFixed(d == null ? 2 : d)).toString().replace('.', ',');
    return s.replace('-', '−');
  }
  // écriture algébrique a + ib lisible
  function cx(a, b, d){
    if (Math.abs(a) < 1e-9) a = 0; if (Math.abs(b) < 1e-9) b = 0;
    var A = fr(a, d), B = fr(Math.abs(b), d);
    var ib = (B === '1' ? 'i' : B + 'i');
    if (b === 0) return A;
    if (a === 0) return (b < 0 ? '−' : '') + ib;
    return A + (b < 0 ? ' − ' : ' + ') + ib;
  }

  var FIG = {
    plan: {
      win: [-5, 5, -4, 4],
      sliders: [
        { k: 'a', label: 'Partie réelle a', min: -4, max: 4, step: 0.5, init: 3 },
        { k: 'b', label: 'Partie imaginaire b', min: -3.5, max: 3.5, step: 0.5, init: 2 }
      ],
      draw: function(g, v){
        var a = v.a, b = v.b;
        g.seg(a, 0, a, b, 'muted', true); g.seg(0, b, a, b, 'muted', true);
        g.seg(a, 0, a, -b, 'muted', true);
        g.arrow(0, 0, a, b, 'pen');
        g.point(a, b, 'pen'); g.label('M(z)', a, b, 'pen');
        g.point(a, -b, 'rouge'); g.label('M′(z̄)', a, -b, 'rouge');
        g.point(-a, -b, 'prof'); g.label('N(−z)', -a, -b, 'prof');
      },
      read: function(v){
        return 'z = ' + cx(v.a, v.b) + '   ;   Re(z) = ' + fr(v.a) + '   ;   Im(z) = ' + fr(v.b)
          + '\nz̄ = ' + cx(v.a, -v.b) + ' (symétrique par rapport à l’axe des réels)   ;   −z = ' + cx(-v.a, -v.b) + ' (symétrique par rapport à O)';
      }
    },
    puissances: {
      win: [-1.8, 1.8, -1.5, 1.5],
      sliders: [{ k: 'n', label: 'Exposant n', min: 0, max: 12, step: 1, init: 0 }],
      P: [[1, 0], [0, 1], [-1, 0], [0, -1]],
      draw: function(g, v){
        var n = v.n, P = this.P, names = ['1', 'i', '−1', '−i'];
        for (var k = 0; k < 4; k++){ g.point(P[k][0], P[k][1], 'muted', true); g.label(names[k], P[k][0], P[k][1], 'muted'); }
        for (var j = 0; j < n; j++){ var p = P[j % 4], q = P[(j + 1) % 4]; g.seg(p[0], p[1], q[0], q[1], 'line'); }
        var r = P[n % 4];
        g.arrow(0, 0, r[0], r[1], 'pen'); g.point(r[0], r[1], 'rouge');
      },
      read: function(v){
        var n = v.n, names = ['1', 'i', '−1', '−i'];
        return 'n = ' + n + ' : n = 4 × ' + Math.floor(n / 4) + ' + ' + (n % 4) + ', donc iⁿ = i' + toSup(n % 4) + ' = ' + names[n % 4];
      }
    },
    vecteur: {
      win: [-2, 6, -2, 5],
      sliders: [
        { k: 'a', label: 'Re(zB)', min: -1.5, max: 5.5, step: 0.5, init: 4 },
        { k: 'b', label: 'Im(zB)', min: -1.5, max: 4.5, step: 0.5, init: 3 }
      ],
      draw: function(g, v){
        var xa = 1, ya = -1, xb = v.a, yb = v.b, xi = (xa + xb) / 2, yi = (ya + yb) / 2;
        g.arrow(0, 0, xb - xa, yb - ya, 'prof', true);
        g.arrow(xa, ya, xb, yb, 'pen');
        g.point(xa, ya, 'ink'); g.label('A', xa, ya, 'ink');
        g.point(xb, yb, 'ink'); g.label('B', xb, yb, 'ink');
        g.point(xi, yi, 'rouge'); g.label('I', xi, yi, 'rouge', (xb - xa) * (yb - ya) >= 0 ? 1 : -1, (xb - xa) * (yb - ya) >= 0 ? 1 : 1);
      },
      read: function(v){
        var dx = v.a - 1, dy = v.b + 1;
        return 'zA = 1 − i   ;   zB = ' + cx(v.a, v.b)
          + '\nAffixe de AB→ : zB − zA = ' + cx(dx, dy) + '   ;   AB = |zB − zA| = ' + fr(Math.sqrt(dx*dx + dy*dy))
          + '\nMilieu I de [AB] : (zA + zB)/2 = ' + cx((1 + v.a) / 2, (v.b - 1) / 2);
      }
    },
    'second-degre': {
      win: [-2.5, 4.5, -3, 3],
      sliders: [{ k: 'c', label: 'Coefficient c', min: -3, max: 6, step: 0.25, init: 5 }],
      roots: function(c){
        var D = 4 - 4 * c;
        if (D >= 0){ var s = Math.sqrt(D) / 2; return { D: D, r: [[1 - s, 0], [1 + s, 0]] }; }
        var t = Math.sqrt(-D) / 2; return { D: D, r: [[1, -t], [1, t]] };
      },
      draw: function(g, v){
        var R = this.roots(v.c);
        g.vline(1, 'line', true);
        g.point(R.r[0][0], R.r[0][1], 'rouge'); g.point(R.r[1][0], R.r[1][1], 'pen');
        if (R.D < 0){ g.label('z₁', R.r[1][0], R.r[1][1], 'pen'); g.label('z₂', R.r[0][0], R.r[0][1], 'rouge'); }
      },
      read: function(v){
        var R = this.roots(v.c), D = R.D;
        var s = 'z² − 2z + ' + fr(v.c) + ' = 0   ;   Δ = 4 − 4c = ' + fr(D) + '\n';
        if (D > 0) return s + 'Δ > 0 : deux solutions réelles ' + fr(R.r[0][0]) + ' et ' + fr(R.r[1][0]) + ' (sur l’axe des réels).';
        if (D === 0) return s + 'Δ = 0 : une solution double z = 1.';
        return s + 'Δ < 0 : deux solutions conjuguées z₁ = ' + cx(1, R.r[1][1]) + ' et z₂ = ' + cx(1, R.r[0][1]) + ', symétriques par rapport à l’axe des réels.';
      }
    }
  };
  function toSup(n){ return '⁰¹²³'.charAt(n); }

  function niceStep(span){
    var raw = span / 7, p = Math.pow(10, Math.floor(Math.log10(raw))), r = raw / p;
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
    var html = '<canvas class="g-cv" role="img" aria-label="' + echapper(el.dataset.alt || 'Graphique') + '"></canvas>';
    cfg.sliders.forEach(function(s){
      var id = 'g-' + el.dataset.fig + '-' + s.k;
      html += '<div class="g-ctl"><label for="' + id + '">' + s.label + '</label>'
        + '<input type="range" id="' + id + '" data-k="' + s.k + '" min="' + s.min + '" max="' + s.max + '" step="' + s.step + '" value="' + s.init + '"></div>';
    });
    html += '<p class="g-read" aria-live="polite"></p>';
    el.innerHTML = html;
    this.cv = el.querySelector('canvas'); this.inps = el.querySelectorAll('input'); this.out = el.querySelector('.g-read');
    this.inps.forEach(function(i){ i.addEventListener('input', function(){ self.render(); }); });
  }
  Graph.prototype.render = function(){
    var cv = this.cv, W = cv.clientWidth, H = cv.clientHeight;
    if (!W || !H) return;
    var dpr = window.devicePixelRatio || 1;
    if (cv.width !== Math.round(W * dpr) || cv.height !== Math.round(H * dpr)){ cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); }
    var c = cv.getContext('2d'); c.setTransform(dpr, 0, 0, dpr, 0, 0); c.clearRect(0, 0, W, H);
    var cs = getComputedStyle(document.documentElement), col = {};
    ['ink','muted','line','grid','pen','rouge','prof','surface','pen-bg','rouge-bg'].forEach(function(k){ col[k] = cs.getPropertyValue('--' + k).trim() || '#888'; });
    var v = {}; this.inps.forEach(function(i){ v[i.dataset.k] = parseFloat(i.value); });
    var cfg = this.cfg, w = cfg.win, x0 = w[0], x1 = w[1], y0 = w[2], y1 = w[3];
    var pl = 30, pr = 10, pt = 10, pb = 22, iw = W - pl - pr, ih = H - pt - pb;
    // repère orthonormé : on élargit la fenêtre dans la direction qui a de la place
    var k = Math.min(iw / (x1 - x0), ih / (y1 - y0));
    var cxm = (x0 + x1) / 2, cym = (y0 + y1) / 2;
    x0 = cxm - iw / k / 2; x1 = cxm + iw / k / 2; y0 = cym - ih / k / 2; y1 = cym + ih / k / 2;
    function X(x){ return pl + (x - x0) * k; }
    function Y(y){ return H - pb - (y - y0) * k; }
    var font = cs.getPropertyValue('--f-body') || 'sans-serif';
    c.font = '12px ' + font; c.lineJoin = 'round'; c.lineCap = 'round';

    var g = {
      vline: function(x, kk, dash){ c.save(); c.strokeStyle = col[kk]; c.lineWidth = 1.5; if (dash) c.setLineDash([6, 5]); c.beginPath(); c.moveTo(X(x), pt); c.lineTo(X(x), H - pb); c.stroke(); c.restore(); },
      seg: function(xa, ya, xb, yb, kk, dash){ c.save(); c.strokeStyle = col[kk]; c.lineWidth = dash ? 1.3 : 2; if (dash) c.setLineDash([5, 4]); c.beginPath(); c.moveTo(X(xa), Y(ya)); c.lineTo(X(xb), Y(yb)); c.stroke(); c.restore(); },
      arrow: function(xa, ya, xb, yb, kk, dash){
        var ax = X(xa), ay = Y(ya), bx = X(xb), by = Y(yb), L = Math.hypot(bx - ax, by - ay);
        if (L < 2) return;
        var ux = (bx - ax) / L, uy = (by - ay) / L, h = Math.min(11, L / 2);
        c.save(); c.strokeStyle = col[kk]; c.fillStyle = col[kk]; c.lineWidth = 2.2; if (dash) c.setLineDash([6, 4]);
        c.beginPath(); c.moveTo(ax, ay); c.lineTo(bx - ux * h * 0.8, by - uy * h * 0.8); c.stroke(); c.setLineDash([]);
        c.beginPath(); c.moveTo(bx, by); c.lineTo(bx - ux * h - uy * h * 0.45, by - uy * h + ux * h * 0.45); c.lineTo(bx - ux * h + uy * h * 0.45, by - uy * h - ux * h * 0.45); c.closePath(); c.fill(); c.restore();
      },
      point: function(x, y, kk, open){
        c.save(); c.beginPath(); c.arc(X(x), Y(y), 5, 0, 6.2832);
        c.fillStyle = open ? col.surface : col[kk]; c.fill(); c.lineWidth = 2; c.strokeStyle = col[kk]; c.stroke(); c.restore();
      },
      // étiquette placée à l'extérieur, du côté opposé à l'origine
      label: function(s, x, y, kk, fdx, fdy){
        var px = X(x), py = Y(y), dx = fdx || (x >= 0 ? 1 : -1), dy = fdy || (y >= 0 ? -1 : 1);
        c.save(); c.fillStyle = col[kk]; c.font = '700 13px ' + font;
        c.textAlign = dx > 0 ? 'left' : 'right'; c.textBaseline = dy < 0 ? 'bottom' : 'top';
        c.fillText(s, px + dx * 7, py + dy * 5); c.restore();
      }
    };

    // fond, quadrillage, axes
    c.fillStyle = col.surface; c.fillRect(0, 0, W, H);
    var st = niceStep(Math.min(x1 - x0, y1 - y0) * 7 / 6), t;
    c.strokeStyle = col.grid; c.lineWidth = 1; c.fillStyle = col.muted;
    c.textAlign = 'center'; c.textBaseline = 'top';
    for (t = Math.ceil(x0 / st) * st; t <= x1 + 1e-9; t += st){
      c.beginPath(); c.moveTo(X(t), pt); c.lineTo(X(t), H - pb); c.stroke();
      c.fillText(tickLabel(Math.abs(t) < 1e-9 ? 0 : t, st), X(t), H - pb + 5);
    }
    c.textAlign = 'right'; c.textBaseline = 'middle';
    for (t = Math.ceil(y0 / st) * st; t <= y1 + 1e-9; t += st){
      c.beginPath(); c.moveTo(pl, Y(t)); c.lineTo(W - pr, Y(t)); c.stroke();
      if (Math.abs(t) > 1e-9) c.fillText(tickLabel(t, st), pl - 5, Y(t));
    }
    c.textBaseline = 'alphabetic';
    c.strokeStyle = col.muted; c.lineWidth = 1.4;
    c.beginPath(); c.moveTo(pl, Y(0)); c.lineTo(W - pr, Y(0)); c.stroke();
    c.beginPath(); c.moveTo(X(0), pt); c.lineTo(X(0), H - pb); c.stroke();
    c.fillStyle = col.muted; c.font = '600 12px ' + font; c.textAlign = 'right';
    c.fillText('axe des réels', W - pr - 2, Y(0) - 6);
    c.textAlign = 'left'; c.fillText('axe des imaginaires purs', X(0) + 6, pt + 12);

    cfg.draw(g, v);
    this.out.textContent = cfg.read(v);
  };


// Correctif de sécurité : data-alt vient du contenu ; il est échappé avant d'entrer dans innerHTML.
function echapper(texte) {
  return String(texte).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c])
}

export { FIG, Graph }
