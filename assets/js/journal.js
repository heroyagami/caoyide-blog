/* Small reading controls. Articles and navigation remain usable without JavaScript. */
(() => {
  const content = document.querySelector('.main-article .article-content');
  const bar = document.querySelector('.journal-reading-bar');
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const scrollTo = node => node.scrollIntoView({block: 'center', behavior: reduceMotion.matches ? 'auto' : 'smooth'});

  if (bar && content) {
    const font = bar.querySelector('[data-reader-font]');
    const setSize = large => {
      document.documentElement.dataset.readingSize = large ? 'large' : 'normal';
      font.setAttribute('aria-pressed', String(large));
      font.setAttribute('aria-label', large ? '恢复标准正文字号' : '使用大字阅读');
      font.textContent = large ? '标准字号' : '大字';
    };
    let large = false;
    try { large = localStorage.getItem('journal-reading-size') === 'large'; } catch {}
    setSize(large);
    font.hidden = false;
    font.addEventListener('click', () => {
      large = !large;
      setSize(large);
      try { localStorage.setItem('journal-reading-size', large ? 'large' : 'normal'); } catch {}
    });

    const toc = bar.querySelector('.journal-reader-toc');
    if (toc) {
      const summary = toc.querySelector('summary');
      const close = focus => { toc.open = false; if (focus) summary.focus(); };
      toc.addEventListener('click', event => {
        const link = event.target.closest('a[href^="#"]');
        if (!link) return;
        const target = document.getElementById(decodeURIComponent(link.hash.slice(1)));
        if (!target) return;
        event.preventDefault();
        close(false);
        history.pushState(null, '', link.hash);
        target.setAttribute('tabindex', '-1');
        target.focus({preventScroll: true});
        target.scrollIntoView({block: 'start', behavior: reduceMotion.matches ? 'auto' : 'smooth'});
      });
      document.addEventListener('keydown', event => { if (event.key === 'Escape' && toc.open) close(true); });
      document.addEventListener('click', event => { if (toc.open && !toc.contains(event.target)) close(false); });
    }

    const links = [...document.querySelectorAll('.widget--toc a[href^="#"]')];
    const sections = links.map(link => ({link, node: document.getElementById(decodeURIComponent(link.hash.slice(1)))})).filter(item => item.node);
    let active = null;
    let queued = false;
    const update = () => {
      queued = false;
      let current = sections[0];
      for (const section of sections) {
        if (section.node.getBoundingClientRect().top <= 140) current = section;
      }
      if (!current || active === current.link) return;
      active?.removeAttribute('aria-current');
      active = current.link;
      active.setAttribute('aria-current', 'location');
    };
    window.addEventListener('scroll', () => { if (!queued) { queued = true; requestAnimationFrame(update); } }, {passive: true});
    update();
  }

  const query = new URL(location.href).searchParams.get('highlight');
  if (!content || !query) return;
  const words = [...new Set(query.slice(0, 120).split(/\s+/).filter(Boolean))].slice(0, 8).sort((a, b) => b.length - a.length);
  if (!words.length) return;
  const regex = new RegExp(words.map(word => word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|'), 'gi');
  const walker = document.createTreeWalker(content, NodeFilter.SHOW_TEXT, {
    acceptNode: node => node.parentElement?.closest('mark,script,style,code,pre,textarea') ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT
  });
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  const marks = [];
  for (const node of nodes) {
    const text = node.textContent || '';
    regex.lastIndex = 0;
    if (!regex.test(text)) continue;
    regex.lastIndex = 0;
    const fragment = document.createDocumentFragment();
    let offset = 0;
    for (const match of text.matchAll(regex)) {
      fragment.append(text.slice(offset, match.index));
      const mark = document.createElement('mark');
      mark.className = 'journal-search-match';
      mark.textContent = match[0];
      marks.push(mark);
      fragment.append(mark);
      offset = match.index + match[0].length;
    }
    fragment.append(text.slice(offset));
    node.replaceWith(fragment);
  }
  const matches = document.createElement('div');
  matches.className = 'journal-match-bar';
  matches.setAttribute('role', 'region');
  matches.setAttribute('aria-label', '搜索命中位置');
  const status = document.createElement('span');
  status.setAttribute('role', 'status');
  status.textContent = marks.length ? `正文中找到 ${marks.length} 处匹配` : '正文中未找到关键词，已显示完整原文';
  matches.append(status);
  let current = -1;
  const action = (label, handler) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = label;
    button.addEventListener('click', handler);
    matches.append(button);
  };
  const move = delta => {
    if (current >= 0) marks[current].classList.remove('is-current');
    current = (current + delta + marks.length) % marks.length;
    marks[current].classList.add('is-current');
    status.textContent = `第 ${current + 1} / ${marks.length} 处匹配`;
    scrollTo(marks[current]);
  };
  if (marks.length) {
    action('上一处', () => move(current === -1 ? 0 : -1));
    action('下一处', () => move(1));
  }
  action('取消高亮', () => {
    marks.forEach(mark => mark.replaceWith(document.createTextNode(mark.textContent)));
    content.normalize();
    matches.remove();
    const url = new URL(location.href);
    url.searchParams.delete('highlight');
    history.replaceState(null, '', url);
  });
  content.before(matches);
})();
