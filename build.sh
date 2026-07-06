#!/bin/bash
# build.sh — 主站 Hugo + 法条库 VuePress 一次构建脚本
# 用法：bash build.sh（在 caoyide-blog 根目录运行）
#
# 流程：
#   1. 安装正确版本的 Hugo（Cloudflare Pages 忽略 HUGO_VERSION 环境变量）
#   2. 进 law-site/ 装依赖（首次或 lock 变了时）
#   3. VuePress build → law-site/docs/.vuepress/dist/
#   4. 复制 VuePress 输出到 public/laws/（先清空旧产物）
#   5. Hugo build（已配置 ignoreFiles 跳过 content/laws/，不会覆盖）

set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
LAW_SITE_DIR="$ROOT_DIR/law-site"
PUBLIC_DIR="$ROOT_DIR/public"
HUGO_VERSION="${HUGO_VERSION:-0.159.0}"

echo "==> 0. 安装 Hugo $HUGO_VERSION（Cloudflare Pages 环境变量不生效，手动安装）"
# 检测系统和架构
OS="linux"
ARCH="amd64"
if [ "$(uname -m)" = "aarch64" ] || [ "$(uname -m)" = "arm64" ]; then
    ARCH="arm64"
fi

HUGO_BIN="$ROOT_DIR/.hugo/hugo"
mkdir -p "$ROOT_DIR/.hugo"

# 检查是否已安装正确版本
if [ -f "$HUGO_BIN" ] && "$HUGO_BIN" version 2>/dev/null | grep -q "$HUGO_VERSION"; then
    echo "    Hugo $HUGO_VERSION 已安装"
else
    echo "    下载 Hugo $HUGO_VERSION..."
    HUGO_URL="https://github.com/gohugoio/hugo/releases/download/v${HUGO_VERSION}/hugo_extended_${HUGO_VERSION}_${OS}-${ARCH}.tar.gz"
    curl -sL "$HUGO_URL" | tar -xz -C "$ROOT_DIR/.hugo" hugo
    chmod +x "$HUGO_BIN"
    echo "    Hugo $HUGO_VERSION 安装完成"
fi

# 将 Hugo 加入 PATH
export PATH="$ROOT_DIR/.hugo:$PATH"

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

echo "==> 3.5 生成法条库 sitemap"
# 从 public/laws/ 的 HTML 文件反推 URL，生成 laws/sitemap.xml
# 零依赖，纯 shell，Hugo build 前执行以免被 Hugo 覆盖
bash "$ROOT_DIR/scripts/generate-laws-sitemap.sh" "$PUBLIC_DIR" "https://caoyide.com"

echo "==> 4. Hugo build（主站）"
cd "$ROOT_DIR"
hugo --gc --minify

echo ""
echo "✅ 构建完成！"
echo "   主站输出：$PUBLIC_DIR/"
echo "   法条库：$PUBLIC_DIR/laws/"
