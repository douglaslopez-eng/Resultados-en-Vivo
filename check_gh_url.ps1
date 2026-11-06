$res = Invoke-RestMethod -Uri "https://douglaslopez-eng.github.io/Resultados-en-Vivo/index.json?v=$(Get-Random)"
$res | ConvertTo-Json
