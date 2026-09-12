# 常青法律文章生产规范

本规范用于“内容缺口 → 常青文章”自动化，不改变网站现有视觉布局。

## 1. 选题来源

任务首先读取：

- `https://caoyide.com/legal-content-gaps.json`
- 若线上 feed 暂不可用，则读取仓库构建逻辑所依赖的 `data/legal-search-intents.json` 与 `data/content-gap-priorities.json`。

原则：优先补 `priorityBand=high` 且当前没有文章覆盖的 gap；同一 intent 不重复生产。

## 2. 发布路径

草稿保存到：

`content/posts/YYYY-MM-DD-<slug>.md`

使用普通 `posts` 栏目，不新增页面布局。

## 3. 必需 Front Matter

```toml
+++
title = '...'
date = '...'
draft = true
author = '曹义德律师'
type = 'evergreen'
tags = []
categories = []
description = '...'
slug = '...'
intent_id = 'https://caoyide.com/#intent-...'
topic_id = 'https://caoyide.com/#topic-...'
practice_area = '刑事辩护'
related_laws = []
review_status = 'pending'
reviewed_by = ''
last_verified = ''
legal_sources = []
case_sources = []
+++
```

`intent_id`、`topic_id`、`practice_area` 必须来自现有机器配置，不得自行杜撰。

## 4. 法律来源规则

- `related_laws` 只能使用现有知识图谱或法律文库中能够确认存在的路径。
- `legal_sources` 写明实际核验过的现行有效法律、司法解释、规范性文件或权威案例来源。
- 不确定的法条不要猜；宁可留空并保持草稿状态。

## 5. 审核与发布

自动任务默认只生成：

- `draft = true`
- `review_status = 'pending'`

只有律师人工核验后，才允许改为：

- `draft = false`
- `review_status = 'verified'`
- 填写 `reviewed_by`
- 填写 `last_verified`

CI 会阻止缺少上述字段的常青文章公开发布。

## 6. 写作结构

常青文章不追热点，重点回答一个明确法律问题。推荐结构：

1. 直接回答结论边界；
2. 适用条件；
3. 法律依据；
4. 证据与程序；
5. 常见误区；
6. 实务建议；
7. 风险提示。

禁止虚构办案经历、当事人事实或裁判结果。
