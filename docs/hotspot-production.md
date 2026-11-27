# 热点深度统一内容入口（直接归档契约）

目标：在 caoyide-blog 统一存储、管理并发布法律日报、热点深度和常青实务。热点内容原路径保持 content/hotspot-daily/YYYY/MM/YYYY-MM-DD.md，现有页面地址不变。DailyNews 的原始写作定位和公众号稿件格式保留；不将热点写作变成法律资讯汇总。

## 现有状态与切换条件

历史迁移已经完成固定源版本的46份文件逐字节核验（仅添加稳定 URL），站点构建通过。data/hotspot-source.json 的 mode=site 时，原同步脚本不联网、不修改内容；mode=legacy 可用于明确回退。先启用 site 冻结历史镜像，再更新云任务目标，确认下一次直接写入和网站结果后才考虑归档旧仓库。切换前后均不补录历史任务。

## 直接写入契约（切换后适用）

- 同一北京日期只写一份 Markdown；只处理本次计划周期。目标路径与既有镜像一致，不新建栏目、不改变文章 URL。
- 完整正文沿用热点雷达、事实核查、原创观点与公众号编辑审稿；每篇真实来源以 HTML 注释记录。首选 3–6 篇，不凑数、不杜撰。
- YAML 保留 title、date、draft: false、author、type: hotspot-deep-daily、categories、tags、description；另加唯一的 url: "/hotspot-daily/YYYY/MM/YYYY-MM-DD/"。正文首行 # 今日热点深度文章池，文章以 ## 1. 等标题开篇。未经审核不得直接作为已发布内容写入主分支。
- 提交前先读取现有文件；只有明确 NOT_FOUND 才创建，更新须绑定 blob SHA。网络不明确时先回读，不盲重试或绕过审批。写入后立即回读完整 Markdown 并记录真实 commit SHA；归档成功不等于网站实际可见。
- 保持原定任务时间，不重复发布、不补录过期任务。不得改动法律日报、常青文章或其他栏目。

## 核验

使用 scripts/audit-hotspot-migration.py 离线核对 data/dailynews-archive-manifest.json。46份历史热点文章以网站版本和逆向 URL 转换恢复原始字节；旧库其余3份文件完整保存在 docs/dailynews-legacy/（不进入 Hugo content，避免重复发布）。所有49份文件均以固定来源 Git blob SHA 核验，无需访问旧库。历史基线不应无意修改；合法修订应另行记录。部署流程保留；旧同步调度在 site 模式下安全空转，首次直接归档实际成功前仍保留 legacy 回退能力及旧仓库。
