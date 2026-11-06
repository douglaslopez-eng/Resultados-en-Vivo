try {
    $res = Invoke-RestMethod -Uri "https://atletismopro-resultados.pages.dev/index.json" -Method Get
    $res | ConvertTo-Json -Depth 3
} catch {
    Write-Output $_.Exception.Message
}
