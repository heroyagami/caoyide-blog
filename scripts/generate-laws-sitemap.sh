#!/bin/bash
# scripts/generate-laws-sitemap.sh
# 从 VuePress 构建产物 public/laws/ 的 HTML 文件反推 URL，
# 生成法条库专属 sitemap.xml（零依赖，纯 shell）
#
# 用法：bash scripts/generate-laws-sitemap.sh <public-dir> <base-url>
# 示例：bash scripts/generate-laws-sitemap.sh public https://caoyide.com

set -e

PUBLIC_DIR="${1:?用法: $0 <public-dir> <base-url>}"
BASE_URL="${2:?用法: $0 <public-dir> <base-url>}"
LAWS_DIR="$PUBLIC_DIR/laws"

if [ ! -d "$LAWS_DIR" ]; then
    echo "    ⚠️  $LAWS_DIR 不存在，跳过 laws sitemap 生成"
    exit 0
fi

SITEMAP="$LAWS_DIR/sitemap.xml"

echo "    → 生成 laws sitemap..."

# 收集所有子目录中的 index.html，提取相对路径转 URL
# VuePress 生成目录式结构: laws/constitution/index.html → /laws/constitution/
# 排除根目录的 index.html（sitemap 首页单独处理）
URLS=$(
    find "$LAWS_DIR" -name 'index.html' ! -path '*/assets/*' \
        | sed "s|^$LAWS_DIR/||; s|/index\.html$||" \
        | sort
)

# 写 sitemap.xml
cat > "$SITEMAP" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>${BASE_URL}/laws/</loc>
  </url>
EOF

while IFS= read -r path; do
    # 跳过空行和首页（已在前面写入）
    [ -z "$path" ] && continue
    [ "$path" = "index" ] && continue
    cat >> "$SITEMAP" <<EOF
  <url>
    <loc>${BASE_URL}/laws/${path}/</loc>
  </url>
EOF
done <<< "$URLS"

cat >> "$SITEMAP" <<EOF
</urlset>
EOF

# 统计行数验证
URL_COUNT=$(grep -c '<loc>' "$SITEMAP")
echo "    ✅ laws sitemap 生成完毕：$URL_COUNT 个 URL → $SITEMAP"
