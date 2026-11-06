$json = Get-Content 'dist\config.json' -Raw | ConvertFrom-Json
$url = "$($json.supabase_url)/storage/v1/object/$($json.supabase_bucket)/indice_competencias.json"
$headers = @{
    "Authorization" = "Bearer $($json.supabase_key)"
    "Content-Type" = "application/json; charset=utf-8"
    "x-upsert" = "true"
}

$bytes = [System.IO.File]::ReadAllBytes("dist\web_results\index.json")
$res = Invoke-RestMethod -Uri $url -Method Put -Headers $headers -Body $bytes
Write-Output "Indice Supabase UTF-8 OK"
