param(
    [string]$SiteUrl = "https://caoyide.com",
    [string]$SitemapUrl = "https://caoyide.com/sitemap.xml"
)

$ErrorActionPreference = "Stop"
$key = "7c45bc0bee954102a00903cd12102e9c"
$siteUri = [Uri]$SiteUrl
$sitemap = Invoke-RestMethod -Uri $SitemapUrl -Method Get
$urls = @($sitemap.urlset.url.loc | ForEach-Object { [string]$_ } | Sort-Object -Unique)

if ($urls.Count -eq 0) {
    throw "Sitemap 中没有可提交的网址：$SitemapUrl"
}

$payload = @{
    host        = $siteUri.Host
    key         = $key
    keyLocation = "$($siteUri.Scheme)://$($siteUri.Host)/$key.txt"
    urlList     = $urls
} | ConvertTo-Json -Depth 4

$response = Invoke-WebRequest `
    -Uri "https://api.indexnow.org/indexnow" `
    -Method Post `
    -ContentType "application/json; charset=utf-8" `
    -Body $payload

Write-Output "IndexNow 提交成功：HTTP $($response.StatusCode)，共 $($urls.Count) 个网址。"
