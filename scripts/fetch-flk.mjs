#!/usr/bin/env node
/**
 * fetch-flk.mjs — 抓全国人大常委会国家法律法规数据库最新法规
 * 输出 RSS 2.0 XML 到 public/flk-rss.xml
 *
 * 用法：
 *   node scripts/fetch-flk.mjs
 *
 * 每天早上跑一次（自动/手动都行），生成新法规推送 RSS
 * 用户在 folo app 订阅 https://caoyide.com/flk-rss.xml 即可
 *
 * 依赖：playwright-core（用户机器上的 Edge）
 */

import { chromium } from "playwright-core";
import { writeFileSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, join } from "path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = join(__dirname, "..");
const OUTPUT_PATH = join(PROJECT_ROOT, "static", "flk-rss.xml");

const SITE_URL = "https://caoyide.com";
const RSS_TITLE = "国家法律法规数据库 · 最新法规速递";
const RSS_DESC = "全国人大常委会国家法律法规数据库 · 每日最新通过的法规（由 caoyide.com 自动同步）";
const API = "https://flk.npc.gov.cn/law-search/search/list";

/**
 * 用 Playwright 真实打开 flk.npc.gov.cn 拿 cookie + session
 * 然后调真实 API 端点
 */
async function fetchRecentLaws() {
  const browser = await chromium.launch({
    executablePath: "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
    headless: true,
  });
  try {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();

    // 打开 search 页面拿 session/cookie
    await page.goto("https://flk.npc.gov.cn/search", { waitUntil: "networkidle", timeout: 30000 });
    await page.waitForTimeout(2000);

    // 调搜索 API 拿按 gbrq 倒序的最新 30 条
    const result = await page.evaluate(async (url) => {
      const res = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json;charset=UTF-8",
          Referer: "https://flk.npc.gov.cn/search",
        },
        body: JSON.stringify({
          searchRange: 1,
          sxrq: [],
          gbrq: [],
          searchType: 2,
          sxx: [],
          gbrqYear: [],
          flfgCodeId: [],
          zdjgCodeId: [],
          searchContent: "",
          orderByParam: { order: "-1", sort: "gbrq" },
          pageNum: 1,
          pageSize: 30,
        }),
      });
      return await res.text();
    }, API);

    return JSON.parse(result);
  } finally {
    await browser.close();
  }
}

/**
 * XML escape
 */
function esc(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

/**
 * 把法规数据转成 RSS 2.0 XML
 */
function buildRSS(laws) {
  const now = new Date().toUTCString();
  const items = laws.map((law) => {
    const link = `${SITE_URL}/posts/`;
    // npc 法规没有公开外链 URL — 用 caoyide 自己的搜索页 + 关键词
    const title = `[${law.flxz}] ${law.title}`;
    const desc = [
      `📅 公布日期：${law.gbrq || "未知"}`,
      `🗓 施行日期：${law.sxrq || "未知"}`,
      `🏛 制定机关：${law.zdjgName || "未知"}`,
      `📂 分类：${law.flxz || "未知"}`,
      "",
      `▎ flk.npc.gov.cn 全文链接：https://flk.npc.gov.cn/detail2.html?${law.bbbs}`,
    ].join("\n");
    return `    <item>
      <title>${esc(title)}</title>
      <link>${esc(link)}</link>
      <description><![CDATA[${desc}]]></description>
      <category>${esc(law.flxz)}</category>
      <author>npc.gov.cn</author>
      <guid isPermaLink="false">npc-${esc(law.bbbs)}</guid>
      <pubDate>${new Date(law.gbrq || Date.now()).toUTCString()}</pubDate>
    </item>`;
  });

  return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${esc(RSS_TITLE)}</title>
    <link>${SITE_URL}/flk-rss.xml</link>
    <atom:link href="${SITE_URL}/flk-rss.xml" rel="self" type="application/rss+xml" />
    <description>${esc(RSS_DESC)}</description>
    <language>zh-CN</language>
    <lastBuildDate>${now}</lastBuildDate>
    <generator>caoyide-blog flk fetcher v1.0</generator>
    <image>
      <url>${SITE_URL}/img/og-cover.jpg</url>
      <title>${esc(RSS_TITLE)}</title>
      <link>${SITE_URL}</link>
    </image>
${items.join("\n")}
  </channel>
</rss>
`;
}

async function main() {
  console.log("🚀 抓取 flk.npc.gov.cn 最新法规...");
  const data = await fetchRecentLaws();
  console.log(`  数据库共 ${data.total} 条法规`);
  console.log(`  拿到最新 ${data.rows.length} 条`);
  console.log(`  最新一条：${data.rows[0]?.gbrq} - ${data.rows[0]?.title}`);

  const xml = buildRSS(data.rows);
  writeFileSync(OUTPUT_PATH, xml, "utf-8");
  console.log(`\n✅ RSS XML 已生成: ${OUTPUT_PATH}`);
  console.log(`  大小: ${xml.length} bytes`);
  console.log(`  条目数: ${data.rows.length}`);
  console.log(`\n📡 在 folo 订阅: ${SITE_URL}/flk-rss.xml`);
}

main().catch((err) => {
  console.error("❌ 错误:", err);
  process.exit(1);
});
