#!/usr/bin/env node
/**
 * gen-laws-md.mjs — 扫描 themes-data/laws/docs/ → 为每部法律生成 content/laws/{cat}/{name}.md
 *
 * 用法：
 *   node scripts/gen-laws-md.mjs              # 生成全部
 *   node scripts/gen-laws-md.mjs --dry-run    # 只看会生成什么
 *
 * 智能处理大部头法律（如 civil-code 有 8 编）：
 *   - 单文件法律（如 company-law）→ 指向 README.md
 *   - 多文件法律（civil-code/01-...08-...md）→ 为每个子文件生成独立页
 *
 * 产出：content/laws/{cat}/{name}.md
 *       Hugo 用 layouts/_default/single.html（law_file 字段）渲染
 */

import { readdirSync, statSync, readFileSync, writeFileSync, existsSync, mkdirSync } from "fs";
import { join } from "path";

const PROJECT_ROOT = process.cwd();
const LAWS_SRC = join(PROJECT_ROOT, "themes-data", "laws", "docs");
const LAWS_DST = join(PROJECT_ROOT, "content", "laws");

const CATEGORY_MAP = {
  "constitution": "宪法",
  "constitutional-relevance": "宪法相关法",
  "civil-and-commercial": "民商法",
  "criminal-law": "刑法",
  "administrative": "行政法",
  "economic": "经济法",
  "procedural": "程序法",
  "social": "社会法",
};

const args = process.argv.slice(2);
const dryRun = args.includes("--dry-run");

const SPECIAL_NAMES = {
  "civil-code": "民法典", "criminal-law": "刑法", "company-law": "公司法",
  "labor-contract-law": "劳动合同法", "labor-law": "劳动法", "marriage-law": "婚姻法",
  "property-law": "物权法", "insurance-law": "保险法", "securities-law": "证券法",
  "constitution": "宪法", "copyright-law": "著作权法", "trademark-law": "商标法",
  "patent-law": "专利法", "tort-liability": "侵权责任法",
  "general-principles": "一般规定", "property-rights": "物权", "contracts": "合同",
  "personality-rights": "人格权", "marriage-and-family": "婚姻家庭", "inheritance": "继承",
  "tort-liability": "侵权责任", "supplementary": "附则",
};

function humanize(s) {
  if (SPECIAL_NAMES[s]) return SPECIAL_NAMES[s];
  // 处理 "01-general-principles" → "第一编 总则"
  const m = s.match(/^(\d+)-(.+)$/);
  if (m) {
    const num = ["", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十"][parseInt(m[1])] || m[1];
    // 先查整体翻译（如 "marriage-and-family" 整体在 SPECIAL_NAMES 中）
    if (SPECIAL_NAMES[m[2]]) {
      return `第${num}编 ${SPECIAL_NAMES[m[2]]}`;
    }
    const sub = m[2].split("-").map(w => SPECIAL_NAMES[w] || w).join(" ");
    return `第${num}编 ${sub}`;
  }
  return s.split("-").map(w => SPECIAL_NAMES[w] || w).join(" ");
}

function cleanText(s, maxLen = 200) {
  // 去掉 markdown 标记（# ** * _ ` [ ] ( ) > 等），保留纯文本
  return s
    .replace(/^#+\s*/gm, '')           // 标题
    .replace(/\*\*([^*]+)\*\*/g, '$1')  // 粗体
    .replace(/\*([^*]+)\*/g, '$1')     // 斜体
    .replace(/`([^`]+)`/g, '$1')       // 行内 code
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')  // 链接
    .replace(/\s+/g, ' ')              // 多空白合一
    .trim()
    .slice(0, maxLen);
}

function extractSummary(content, maxLen = 200) {
  // 取 H1 后的前 maxLen 字符作为摘要
  const lines = content.split('\n');
  let h1 = '';
  let bodyStart = 0;
  for (let i = 0; i < lines.length; i++) {
    if (/^#\s+/.test(lines[i])) {
      h1 = lines[i].replace(/^#\s+/, '').trim();
      bodyStart = i + 1;
      break;
    }
  }
  const body = lines.slice(bodyStart).join('\n');
  const cleaned = cleanText(body, maxLen);
  return h1 ? `${h1} ${cleaned}`.slice(0, maxLen + 50) : cleaned;
}

function genFrontmatter(category, title, lawFile, summary) {
  return `---
title: "${title.replace(/"/g, '\\"')}"
description: "${category} - ${title.replace(/"/g, '\\"')}"
summary: "${(summary || '').replace(/"/g, '\\"')}"
date: ${new Date().toISOString().slice(0, 10)}
draft: false
category: "${category}"
law_file: "${lawFile}"
---
`;
}

let totalLaws = 0;
const summary = {};
const seenFiles = new Set();  // 防重复

for (const [catDir, catName] of Object.entries(CATEGORY_MAP)) {
  const catSrc = join(LAWS_SRC, catDir);
  if (!existsSync(catSrc)) {
    console.log(`  ⚠️  ${catDir}/ 不存在`);
    continue;
  }

  const lawSets = readdirSync(catSrc).filter(f => statSync(join(catSrc, f)).isDirectory());
  let catCount = 0;

  for (const lawSetName of lawSets) {
    const lawSetPath = join(catSrc, lawSetName);
    const items = readdirSync(lawSetPath);
    const mdFiles = items.filter(f => f.endsWith(".md") && f !== "README.md");
    const subDirs = items.filter(f => statSync(join(lawSetPath, f)).isDirectory());
    const hasReadme = items.includes("README.md");

    // 情况 1：单文件法律（只有 README.md 或 1 个 .md）
    if (mdFiles.length === 0 && subDirs.length === 0 && hasReadme) {
      const mdContent = readFileSync(join(lawSetPath, "README.md"), "utf-8");
      const h1Match = mdContent.match(/^#\s+(.+?)$/m);
      const title = h1Match ? h1Match[1].trim() : humanize(lawSetName);
      const summary = extractSummary(mdContent, 200);
      const lawFile = `${catDir}/${lawSetName}/README.md`;
      const fileDst = join(LAWS_DST, catDir, lawSetName + ".md");
      if (!seenFiles.has(fileDst)) {
        seenFiles.add(fileDst);
        const content = genFrontmatter(catName, title, lawFile, summary);
        if (!dryRun) {
          mkdirSync(join(LAWS_DST, catDir), { recursive: true });
          writeFileSync(fileDst, content, "utf-8");
        }
        catCount++;
      }
      continue;
    }

    // 情况 2：多编法律（如 civil-code 有 01-08 子文件 + README）
    for (const mdFile of mdFiles) {
      const baseName = mdFile.replace(/\.md$/, "");  // "05-marriage-and-family"
      const mdContent = readFileSync(join(lawSetPath, mdFile), "utf-8");
      const h1Match = mdContent.match(/^#\s+(.+?)$/m);
      const title = h1Match ? h1Match[1].trim() : (humanize(baseName) === humanize(lawSetName) ? humanize(lawSetName) : humanize(baseName));
      const summary = extractSummary(mdContent, 200);
      const lawFile = `${catDir}/${lawSetName}/${mdFile}`;
      const fileDst = join(LAWS_DST, catDir, `${lawSetName}--${baseName}.md`);
      if (!seenFiles.has(fileDst)) {
        seenFiles.add(fileDst);
        const content = genFrontmatter(catName, title, lawFile, summary);
        if (!dryRun) {
          mkdirSync(join(LAWS_DST, catDir), { recursive: true });
          writeFileSync(fileDst, content, "utf-8");
        }
        catCount++;
      }
    }

    // 情况 3：子目录（如 criminal-law/amendment/）→ 视为单独法律
    for (const subDir of subDirs) {
      const subPath = join(lawSetPath, subDir);
      const subItems = readdirSync(subPath);
      const subMds = subItems.filter(f => f.endsWith(".md"));
      const subHasReadme = subItems.includes("README.md");
      const targetFile = subHasReadme ? "README.md" : (subMds[0] || "");
      if (!targetFile) continue;
      const mdContent = readFileSync(join(subPath, targetFile), "utf-8");
      const h1Match = mdContent.match(/^#\s+(.+?)$/m);
      const title = h1Match ? h1Match[1].trim() : humanize(subDir);
      const summary = extractSummary(mdContent, 200);
      const lawFile = `${catDir}/${lawSetName}/${subDir}/${targetFile}`;
      const fileDst = join(LAWS_DST, catDir, `${lawSetName}--${subDir}.md`);
      if (!seenFiles.has(fileDst)) {
        seenFiles.add(fileDst);
        const content = genFrontmatter(catName, title, lawFile, summary);
        if (!dryRun) {
          mkdirSync(join(LAWS_DST, catDir), { recursive: true });
          writeFileSync(fileDst, content, "utf-8");
        }
        catCount++;
      }
    }
  }

  summary[catName] = catCount;
  totalLaws += catCount;
  console.log(`📂 ${catName} (${catDir}/): ${catCount} 部/编`);
}

console.log(`\n${dryRun ? "🔍 预览" : "✅ 生成"}：${totalLaws} 个内容页${dryRun ? "（dry-run，未写）" : ""}`);
console.log("分类统计：");
for (const [cat, n] of Object.entries(summary)) {
  console.log(`  ${cat}: ${n} 部/编`);
}

if (dryRun) {
  console.log(`\n💡 确认无误后，去掉 --dry-run 真正生成`);
}
