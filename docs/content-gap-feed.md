# 法律内容缺口 Feed 接入规范

本站构建后会生成稳定机器接口：

`https://caoyide.com/legal-content-gaps.json`

该接口用于让外部日报/公众号/口播选题任务知道：当前网站还缺哪些用户正在搜索的法律问题答案。

## 推荐任务逻辑

1. 每次选题前先读取 `legal-content-gaps.json`。
2. 优先查看 `priorityScore` 从高到低的缺口。
3. 再结合当天热点、事实可核验性、曹义德律师专业相关性决定是否采用。
4. 不因为存在缺口就强行写稿；热点不匹配时可以继续使用当天更重要的法律新闻。
5. 如采用缺口，优先沿用 `searchIntent` / `recommendedTitle`，并参考 `parentTopic`、`practiceArea`。
6. `suggestedLaws` 只代表现有知识图谱中已经确认与上级主题有关的法律，不等于文章最终法律依据。正式稿仍必须逐条核验法条与案例。
7. 新文章发布后，下一次网站构建会重新计算缺口；已经被可靠文章覆盖的意图会自动从 feed 中消失。

## Feed 字段

- `searchIntent`：真实用户问题表达。
- `priorityScore`：0–100 的内容优先级。
- `parentTopic`：上一级法律主题。
- `practiceArea`：对应曹义德律师专业领域。
- `suggestedLaws`：仅来自现有知识图谱的已确认法律候选。
- `scoreBreakdown`：优先级构成，便于审计。

## 重要边界

该 feed 是选题辅助，不是法律结论来源。任何公开文章仍应执行现有的事实、法条、案例和律师审核门禁。
