// @ts-nocheck
// 曹义德律师 - 法律文库 VuePress 客户端配置
// 保持零第三方统计，同时把主站文章与法条页做双向联动。
import { defineClientConfig } from "@vuepress/client";

let backlinkDataPromise = null;

function ensureBacklinkStyles() {
  if (typeof document === "undefined" || document.getElementById("law-backlink-styles")) return;
  const style = document.createElement("style");
  style.id = "law-backlink-styles";
  style.textContent = `
    .law-article-backlinks{margin:2rem 0 0;padding:1.1rem 1.2rem;border:1px solid #dbe4f0;border-radius:14px;background:#f8fbff}
    .law-article-backlinks h2{margin:0 0 .35rem!important;border:0!important;font-size:1.08rem!important;color:#0f2748}
    .law-article-backlinks-intro{margin:.2rem 0 .75rem;color:#64748b;font-size:.88rem}
    .law-article-backlinks ul{list-style:none;margin:0;padding:0;display:grid;gap:.5rem}
    .law-article-backlinks li{display:flex;justify-content:space-between;gap:1rem;align-items:baseline;padding:.55rem .65rem;border-radius:9px;background:#fff}
    .law-article-backlinks a{text-decoration:none!important;font-weight:600}
    .law-article-backlinks li span{white-space:nowrap;color:#94a3b8;font-size:.76rem}
    html.dark .law-article-backlinks{border-color:rgba(148,163,184,.16);background:#111827}
    html.dark .law-article-backlinks h2{color:#f1f5f9}
    html.dark .law-article-backlinks li{background:#0f172a}
    @media(max-width:560px){.law-article-backlinks li{display:grid;gap:.2rem}}
  `;
  document.head.appendChild(style);
}

function loadBacklinks() {
  if (!backlinkDataPromise) {
    backlinkDataPromise = fetch("/laws/article-backlinks.json", { cache: "no-cache" })
      .then((res) => (res.ok ? res.json() : {}))
      .catch(() => ({}));
  }
  return backlinkDataPromise;
}

async function renderLawBacklinks() {
  if (typeof window === "undefined") return;
  ensureBacklinkStyles();

  document.querySelectorAll(".law-article-backlinks").forEach((node) => node.remove());

  const data = await loadBacklinks();
  const path = window.location.pathname;
  const candidates = [
    path,
    path.endsWith("/") ? path.slice(0, -1) : path + "/",
    path.endsWith(".html") ? path.replace(/\.html$/, "/") : path.replace(/\/$/, ".html"),
  ];
  let items = [];
  for (const key of candidates) {
    if (Array.isArray(data[key]) && data[key].length) {
      items = data[key];
      break;
    }
  }
  if (!items.length) return;

  const container = document.querySelector(".theme-default-content") || document.querySelector("main");
  if (!container) return;

  const section = document.createElement("section");
  section.className = "law-article-backlinks";
  section.setAttribute("aria-label", "曹义德律师相关文章");

  const title = document.createElement("h2");
  title.textContent = "曹义德律师相关文章";
  section.appendChild(title);

  const intro = document.createElement("p");
  intro.className = "law-article-backlinks-intro";
  intro.textContent = "以下文章引用或讨论了本页法律规定，可结合具体问题继续阅读。";
  section.appendChild(intro);

  const list = document.createElement("ul");
  items.slice(0, 8).forEach((item) => {
    const li = document.createElement("li");
    const a = document.createElement("a");
    a.href = item.url;
    a.textContent = item.title;
    li.appendChild(a);
    if (item.date) {
      const time = document.createElement("span");
      time.textContent = item.date;
      li.appendChild(time);
    }
    list.appendChild(li);
  });
  section.appendChild(list);
  container.appendChild(section);
}

export default defineClientConfig({
  enhance({ router }) {
    if (typeof window === "undefined") return;
    router.isReady().then(() => setTimeout(renderLawBacklinks, 80));
    router.afterEach(() => setTimeout(renderLawBacklinks, 80));
  },
});
