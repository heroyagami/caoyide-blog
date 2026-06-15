#!/bin/bash
# build.sh — 主站 Hugo + 法条库 VuePress 一次构建脚本
# 用法：bash build.sh（在 caoyide-blog 根目录运行）
#
# 流程：
#   1. 进 law-site/ 装依赖（首次或 lock 变了时）
#   2. VuePress build → law-site/docs/.vuepress/dist/
#   3. 复制 VuePress 输出到 public/laws/（先清空旧产物）
#   4. Hugo build（已配置 ignoreFiles 跳过 content/laws/，不会覆盖）

set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
LAW_SITE_DIR="$ROOT_DIR/law-site"
PUBLIC_DIR="$ROOT_DIR/public"

echo "==> 1. 安装/检查 VuePress 依赖"
cd "$LAW_SITE_DIR"
if [ ! -d "node_modules" ] || [ "package.json" -nt "node_modules/.package-lock.json" ]; then
    echo "    安装 npm 依赖（首次或 package.json 变更）"
    npm install --no-audit --no-fund
else
    echo "    依赖已就绪"
fi

echo "==> 2. VuePress build（法条库）"
npx vuepress build docs

echo "==> 3. 复制 VuePress 产物到 public/laws/"
mkdir -p "$PUBLIC_DIR/laws"
# 先清空旧的 laws 目录内容（避免旧版本残留）
rm -rf "$PUBLIC_DIR/laws"/*
cp -r "$LAW_SITE_DIR/docs/.vuepress/dist/." "$PUBLIC_DIR/laws/"

echo "==> 4. Hugo build（主站）"
cd "$ROOT_DIR"
hugo --gc --minify

echo ""
echo "✅ 构建完成！"
echo "   主站输出：$PUBLIC_DIR/"
echo "   法条库：$PUBLIC_DIR/laws/"
