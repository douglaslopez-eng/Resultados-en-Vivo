$url = "https://douglaslopez-eng.github.io/Resultados-en-Vivo/index.json?v=" + [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
$res = Invoke-RestMethod -Uri $url -Method Get
$res | ConvertTo-Json -Depth 3
