#!/bin/bash
# build.sh — 主站 Hugo + 法条库 VuePress 一次构建脚本
# 用法：bash build.sh（在 caoyide-blog 根目录运行）
#
# 流程：
#   1. 安装/复用固定版本 Hugo
#   2. 按 package-lock.json 可复现安装 VuePress 依赖
#   3. VuePress build → law-site/docs/.vuepress/dist/
#   4. 复制 VuePress 输出到 public/laws/（先清空旧产物）
#   5. 生成法条库 sitemap
#   6. Hugo build

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
LAW_SITE_DIR="$ROOT_DIR/law-site"
PUBLIC_DIR="$ROOT_DIR/public"
HUGO_VERSION="${HUGO_VERSION:-0.159.0}"

echo "==> 0. 安装/检查 Hugo $HUGO_VERSION"
OS="linux"
ARCH="amd64"
if [ "$(uname -m)" = "aarch64" ] || [ "$(uname -m)" = "arm64" ]; then
    ARCH="arm64"
fi

HUGO_BIN="$ROOT_DIR/.hugo/hugo"
mkdir -p "$ROOT_DIR/.hugo"

if [ -f "$HUGO_BIN" ] && "$HUGO_BIN" version 2>/dev/null | grep -q "$HUGO_VERSION"; then
    echo "    Hugo $HUGO_VERSION 已就绪"
else
    echo "    下载 Hugo $HUGO_VERSION..."
    HUGO_URL="https://github.com/gohugoio/hugo/releases/download/v${HUGO_VERSION}/hugo_extended_${HUGO_VERSION}_${OS}-${ARCH}.tar.gz"
    curl -fsSL "$HUGO_URL" | tar -xz -C "$ROOT_DIR/.hugo" hugo
    chmod +x "$HUGO_BIN"
fi

export PATH="$ROOT_DIR/.hugo:$PATH"

echo "==> 1. 安装/检查 VuePress 依赖"
cd "$LAW_SITE_DIR"
if [ -f "package-lock.json" ]; then
    if [ ! -d "node_modules" ] || [ "package-lock.json" -nt "node_modules/.package-lock.json" ]; then
        echo "    使用 package-lock.json 执行 npm ci"
        npm ci --no-audit --no-fund
    else
        echo "    依赖已就绪"
    fi
else
    echo "    未发现 package-lock.json，构建中止以避免不可复现依赖"
    exit 1
fi

echo "==> 2. VuePress build（法条库）"
npx vuepress build docs

echo "==> 3. 复制 VuePress 产物到 public/laws/"
mkdir -p "$PUBLIC_DIR/laws"
rm -rf "$PUBLIC_DIR/laws"/*
cp -r "$LAW_SITE_DIR/docs/.vuepress/dist/." "$PUBLIC_DIR/laws/"

echo "==> 4. 生成法条库 sitemap"
bash "$ROOT_DIR/scripts/generate-laws-sitemap.sh" "$PUBLIC_DIR" "https://caoyide.com"

echo "==> 5. Hugo build（主站）"
cd "$ROOT_DIR"
hugo --gc --minify

echo ""
echo "✅ 构建完成！"
echo "   主站输出：$PUBLIC_DIR/"
echo "   法条库：$PUBLIC_DIR/laws/"
