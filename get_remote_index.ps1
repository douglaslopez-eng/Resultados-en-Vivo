$cfg = Get-Content 'dist\config.json' -Raw | ConvertFrom-Json
$token = $cfg.github_token
$headers = @{
    "Authorization" = "Bearer $token"
    "Accept" = "application/vnd.github+json"
}
$res = Invoke-RestMethod -Uri "https://api.github.com/repos/douglaslopez-eng/Resultados-en-Vivo/contents/index.json" -Headers $headers
$decoded = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($res.content))
Write-Output $decoded
