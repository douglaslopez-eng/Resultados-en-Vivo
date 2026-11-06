$json = Get-Content 'dist\config.json' -Raw | ConvertFrom-Json
$token = $json.github_token
$headers = @{
    "Authorization" = "Bearer $token"
    "Accept" = "application/vnd.github+json"
}
$repos = Invoke-RestMethod -Uri "https://api.github.com/user/repos?per_page=30" -Headers $headers
foreach ($r in $repos) {
    Write-Output ($r.full_name + " (pages: " + $r.has_pages + ")")
}
