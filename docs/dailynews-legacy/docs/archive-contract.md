# 云端日报归档约定

目标仓库：heroyagami/DailyNews，默认分支。用户已授权每日生成并归档热点深度日报。

1. 固定路径：content/hotspot-daily/YYYY/MM/YYYY-MM-DD.md，日期使用 Asia/Shanghai。
2. 调用 fetch_file 检查目标：只有明确 NOT_FOUND 才创建；鉴权失败、超时或其他错误不能当作文件不存在。
3. create_file / update_file 的 content 传完整 UTF-8 原文，连接器自行编码；不要手工传 base64。已有文件必须先读取当前正文及 blob SHA，避免覆盖未读取的版本。
4. 创建提交信息为 content: add YYYY-MM-DD hotspot deep daily；修订为 content: update YYYY-MM-DD hotspot deep daily。
5. 提交后从默认分支回读同一路径，与待提交原文逐字比较，并校验日期、front matter、3—6篇非空文章和来源注释；记录真实 commit SHA。只有写入和回读都成功才报告归档成功。
6. 网络超时或 5xx 可有限重试；重试前先回读，防止已提交却重复创建。SHA 冲突须重新读取，不得盲目覆盖。
7. 自动审批拒绝、401、403 必须如实记录原始原因，不得更换接口绕过安全审核，不得把审批拒绝误报为 GitHub 服务故障。
8. 任何归档失败均保留完整 Markdown 和错误信息，不得自行暂停、删除或改期内容生产任务；下一次正常执行时先检查并补交能够恢复的旧稿。旧稿不可恢复时说明，不伪造已生成内容。
