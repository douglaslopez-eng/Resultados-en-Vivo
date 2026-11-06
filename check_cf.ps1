$content = Invoke-RestMethod -Uri "https://atletismopro-resultados.pages.dev/index.json?nocache=$(Get-Random)"
$content | ConvertTo-Json
