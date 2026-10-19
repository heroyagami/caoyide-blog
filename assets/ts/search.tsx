interface PageData {
    title: string; displayTitle?: string; date: string; permalink: string;
    content: string; section?: string; tags?: string[];
}
interface Result { page: PageData; score: number; }
const labels: Record<string, string> = {posts: '实务文章', daily: '法律日报', 'hotspot-daily': '热点深度'};

function element<K extends keyof HTMLElementTagNameMap>(tag: K, className = '', text = ''): HTMLElementTagNameMap[K] {
    const node = document.createElement(tag);
    node.className = className;
    node.textContent = text;
    return node;
}
function highlighted(text: string, words: string[]): DocumentFragment {
    const fragment = document.createDocumentFragment();
    if (!words.length) { fragment.append(text); return fragment; }
    const escaped = words.map(word => word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
    const regex = new RegExp(escaped.join('|'), 'gi');
    let start = 0;
    for (const match of text.matchAll(regex)) {
        fragment.append(text.slice(start, match.index));
        fragment.append(element('mark', '', match[0]));
        start = match.index! + match[0].length;
    }
    fragment.append(text.slice(start));
    return fragment;
}

class Search {
    private dataPromise: Promise<PageData[]> | null = null;
    private sequence = 0;
    private timer = 0;
    private composing = false;
    private results: Result[] = [];
    private shown = 0;
    private words: string[] = [];
    private scope = 'all';
    private sort = 'relevance';
    private readonly batch = 20;
    private readonly input: HTMLInputElement;
    private readonly list = document.querySelector<HTMLElement>('.search-result--list')!;
    private readonly status = document.querySelector<HTMLElement>('.journal-search-status')!;
    private readonly controls = document.querySelector<HTMLElement>('.journal-search-controls')!;
    private readonly sortSelect = document.querySelector<HTMLSelectElement>('#search-sort')!;
    private readonly more = document.querySelector<HTMLButtonElement>('.journal-load-more')!;

    constructor(private form: HTMLFormElement) {
        this.input = form.querySelector('input[name=keyword]')!;
        this.form.addEventListener('submit', event => {
            event.preventDefault();
            if (this.composing) return;
            this.updateURL(false);
            void this.run();
        });
        this.input.addEventListener('compositionstart', () => { this.composing = true; this.cancel(); });
        this.input.addEventListener('compositionend', () => { this.composing = false; this.schedule(); });
        this.input.addEventListener('input', () => { if (!this.composing) this.schedule(); });
        this.controls.querySelectorAll<HTMLButtonElement>('[data-scope]').forEach(button => {
            button.addEventListener('click', () => {
                this.scope = button.dataset.scope!;
                this.updateURL(false);
                void this.run();
            });
        });
        this.sortSelect.addEventListener('change', () => {
            this.sort = this.sortSelect.value;
            this.updateURL(false);
            void this.run();
        });
        this.more.addEventListener('click', () => this.appendBatch(true));
        window.addEventListener('popstate', () => this.readURL());
        this.readURL();
    }
    private cancel() {
        window.clearTimeout(this.timer);
        this.sequence++;
        this.list.removeAttribute('aria-busy');
    }
    private schedule() {
        this.cancel();
        this.updateURL(true);
        if (!this.input.value.trim()) { void this.run(); return; }
        this.timer = window.setTimeout(() => void this.run(), 250);
    }
    private readURL() {
        const params = new URL(location.href).searchParams;
        this.input.value = (params.get('keyword') || '').slice(0, 120);
        const scope = params.get('type') || 'all';
        this.scope = labels[scope] ? scope : 'all';
        this.sort = params.get('sort') === 'date' ? 'date' : 'relevance';
        void this.run();
    }
    private updateURL(replace: boolean) {
        const url = new URL(location.href);
        const values: Record<string, string> = {
            keyword: this.input.value.trim().slice(0, 120),
            type: this.scope === 'all' ? '' : this.scope,
            sort: this.sort === 'date' ? 'date' : ''
        };
        Object.entries(values).forEach(([name, value]) => value ? url.searchParams.set(name, value) : url.searchParams.delete(name));
        if (url.href !== location.href) history[replace ? 'replaceState' : 'pushState'](null, '', url);
    }
    private async getData(): Promise<PageData[]> {
        if (!this.dataPromise) {
            this.dataPromise = (async () => {
                const controller = new AbortController();
                const timeout = window.setTimeout(() => controller.abort(), 12000);
                try {
                    const response = await fetch(this.form.dataset.json!, {signal: controller.signal});
                    if (!response.ok) throw new Error('Search index unavailable');
                    const data: unknown = await response.json();
                    if (!Array.isArray(data)) throw new Error('Invalid search index');
                    return data.filter((item): item is PageData => typeof item.title === 'string' && typeof item.content === 'string' && typeof item.permalink === 'string' && item.permalink.startsWith('/') && !item.permalink.startsWith('//'));
                } finally { window.clearTimeout(timeout); }
            })().catch(error => { this.dataPromise = null; throw error; });
        }
        return this.dataPromise;
    }
    private async run() {
        this.cancel();
        const id = this.sequence;
        this.words = [...new Set(this.input.value.trim().split(/\s+/).filter(Boolean))].slice(0, 8);
        this.controls.hidden = !this.words.length;
        this.sortSelect.value = this.sort;
        this.controls.querySelectorAll<HTMLElement>('[data-scope]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.scope === this.scope)));
        this.list.replaceChildren();
        this.more.hidden = true;
        this.results = [];
        this.shown = 0;
        if (!this.words.length) {
            this.status.textContent = '输入关键词，或从这些常见问题开始。';
            this.suggestions();
            return;
        }
        this.status.textContent = '正在查找文章…';
        this.list.setAttribute('aria-busy', 'true');
        const words = this.words.map(word => word.toLocaleLowerCase());
        const scope = this.scope;
        const sort = this.sort;
        try {
            const data = await this.getData();
            if (id !== this.sequence) return;
            for (const page of data) {
                if (scope !== 'all' && page.section !== scope) continue;
                const title = (page.displayTitle || page.title).toLocaleLowerCase();
                const content = page.content.toLocaleLowerCase();
                const all = title + ' ' + page.title.toLocaleLowerCase() + ' ' + content + ' ' + (page.tags || []).join(' ').toLocaleLowerCase();
                if (!words.every(word => all.includes(word))) continue;
                let score = title.includes(words.join(' ')) ? 100 : 0;
                words.forEach(word => {
                    if (title.includes(word)) score += 50;
                    score += Math.min(8, content.split(word).length - 1);
                });
                this.results.push({page, score});
            }
            this.results.sort((a, b) => (sort === 'date' ? 0 : b.score - a.score) || (b.page.date || '').localeCompare(a.page.date || ''));
            this.list.removeAttribute('aria-busy');
            if (!this.results.length) {
                this.status.textContent = `没有找到${scope === 'all' ? '' : '这类内容中'}与「${this.input.value.trim()}」相关的文章。试试更短的关键词。`;
                if (scope !== 'all') {
                    const reset = element('button', 'journal-text-button', '在全部类型中查找');
                    reset.type = 'button';
                    reset.addEventListener('click', () => { this.scope = 'all'; this.updateURL(false); void this.run(); });
                    this.list.append(reset);
                }
                this.suggestions();
                return;
            }
            this.appendBatch();
        } catch {
            if (id !== this.sequence) return;
            this.list.removeAttribute('aria-busy');
            this.status.textContent = '暂时无法加载搜索内容，你输入的关键词已保留。';
            const retry = element('button', 'journal-text-button', '重新加载');
            retry.type = 'button';
            retry.addEventListener('click', () => void this.run());
            this.list.append(retry);
        }
    }
    private suggestions() {
        const nav = element('nav', 'search-suggestions');
        nav.setAttribute('aria-label', '常见搜索');
        ['劳动争议', '合同', '婚姻家庭', '刑事辩护'].forEach(word => {
            const link = element('a', 'search-suggestion-tag', word);
            link.href = '?keyword=' + encodeURIComponent(word);
            nav.append(link);
        });
        this.list.append(nav);
    }
    private appendBatch(focus = false) {
        const next = this.results.slice(this.shown, this.shown + this.batch);
        const fragment = document.createDocumentFragment();
        next.forEach(({page}) => fragment.append(this.render(page)));
        const first = fragment.querySelector<HTMLAnchorElement>('.article-title a');
        this.list.append(fragment);
        this.shown += next.length;
        this.status.textContent = `找到 ${this.results.length} 篇文章${this.results.length > this.batch ? `，已显示 ${this.shown} 篇` : ''}。`;
        this.more.hidden = this.shown >= this.results.length;
        this.more.textContent = `再显示 ${Math.min(this.batch, this.results.length - this.shown)} 篇`;
        if (focus) first?.focus({preventScroll: true});
    }
    private render(page: PageData): HTMLElement {
        const article = element('article', 'search-result-item');
        const details = element('div', 'article-details');
        const meta = element('div', 'search-meta');
        const date = element('time', 'search-date', (page.date || '').slice(0, 10).replaceAll('-', '.'));
        date.dateTime = (page.date || '').slice(0, 10);
        meta.append(date);
        if (page.section && labels[page.section]) meta.append(element('span', 'search-category', labels[page.section]));
        const heading = element('h2', 'article-title');
        const link = element('a');
        const url = new URL(page.permalink, location.origin);
        url.searchParams.set('highlight', this.words.join(' '));
        link.href = url.pathname + url.search;
        link.append(highlighted(page.displayTitle || page.title, this.words));
        heading.append(link);
        const preview = element('p', 'article-preview');
        let content = page.content.replace(/\s+/g, ' ').trim();
        const titleText = page.title.replace(/\s+/g, ' ').trim();
        if (content.startsWith(titleText)) content = content.slice(titleText.length).trim();
        const lower = content.toLocaleLowerCase();
        const hits = this.words.map(word => lower.indexOf(word.toLocaleLowerCase())).filter(index => index >= 0);
        const start = hits.length ? Math.max(0, Math.min(...hits) - 30) : 0;
        preview.append(highlighted((start ? '…' : '') + content.slice(start, start + 150) + (content.length > start + 150 ? '…' : ''), this.words));
        details.append(meta, heading, preview);
        article.append(details);
        return article;
    }
}

const form = document.querySelector<HTMLFormElement>('.template-search .search-form');
if (form) new Search(form);
export default Search;
