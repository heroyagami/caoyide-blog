// @ts-nocheck
// 曹义德律师 - 法律文库 VuePress 客户端配置
// 保持零第三方统计，同时把主站文章与法条页做双向联动。
import { defineClientConfig } from "@vuepress/client";

let backlinkDataPromise = null;

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

  document.querySelectorAll(".law-article-backlinks").forEach((node) => node.remove());

  const data = await loadBacklinks();
  let path = window.location.pathname;
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
