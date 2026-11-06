$url = "https://atletismopro-resultados.pages.dev/index.json?v=" + [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
$res = Invoke-RestMethod -Uri $url -Method Get
$res | ConvertTo-Json -Depth 3
