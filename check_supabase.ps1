$json = Get-Content 'dist\config.json' -Raw | ConvertFrom-Json
$url = "$($json.supabase_url)/storage/v1/object/public/$($json.supabase_bucket)/indice_competencias.json?v=$(Get-Random)"
$res = Invoke-RestMethod -Uri $url
$res | ConvertTo-Json
