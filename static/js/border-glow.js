/* BorderGlow vanilla port — 30 行 JS，无依赖
   监听 .border-glow-card 的 pointermove，更新 2 个 CSS vars
   - --edge-proximity  (0-100, 越靠近边缘越大)
   - --cursor-angle    (0-360deg, 相对卡片中心) */
(function() {
  function track(card) {
    card.addEventListener('pointermove', function(e) {
      var r = card.getBoundingClientRect();
      var x = e.clientX - r.left, y = e.clientY - r.top;
      var cx = r.width / 2, cy = r.height / 2;
      var dx = x - cx, dy = y - cy;
      var kx = dx !== 0 ? cx / Math.abs(dx) : Infinity;
      var ky = dy !== 0 ? cy / Math.abs(dy) : Infinity;
      var edge = Math.min(Math.max(1 / Math.min(kx, ky), 0), 1) * 100;
      var deg = Math.atan2(dy, dx) * 180 / Math.PI + 90;
      if (deg < 0) deg += 360;
      card.style.setProperty('--edge-proximity', edge.toFixed(2));
      card.style.setProperty('--cursor-angle', deg.toFixed(2) + 'deg');
    });
  }

  function init() {
    var cards = document.querySelectorAll('.border-glow-card');
    for (var i = 0; i < cards.length; i++) {
      // 确保内部结构存在（partial 模板负责）
      if (!cards[i].querySelector('.edge-light')) {
        var light = document.createElement('span');
        light.className = 'edge-light';
        cards[i].insertBefore(light, cards[i].firstChild);
      }
      if (!cards[i].querySelector('.border-glow-inner')) {
        // 兼容：原 tile 已有 <article-details>，包一层
        var inner = document.createElement('div');
        inner.className = 'border-glow-inner';
        while (cards[i].firstChild) inner.appendChild(cards[i].firstChild);
        cards[i].appendChild(inner);
      }
      track(cards[i]);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
  // 兼容 Hugo 异步加载的页面片段
  document.addEventListener('htmx:afterSwap', init);
  document.addEventListener('infinite-scroll-loaded', init);
})();
