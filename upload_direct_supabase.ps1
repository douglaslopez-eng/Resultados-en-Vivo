$json = Get-Content 'dist\config.json' -Raw | ConvertFrom-Json
$url = "$($json.supabase_url)/storage/v1/object/$($json.supabase_bucket)/indice_competencias.json"
$headers = @{
    "Authorization" = "Bearer $($json.supabase_key)"
    "Content-Type" = "application/json"
    "x-upsert" = "true"
}

$localPath = Get-ChildItem -Path "dist\web_results" -Filter "*SWORDFISH*.json" | Select-Object -ExpandProperty FullName
$bytesSw = [System.IO.File]::ReadAllBytes($localPath)
$swUrl = "$($json.supabase_url)/storage/v1/object/$($json.supabase_bucket)/Torneo_de_Natacion_Academia_SWORDFISH.json"
$resSw = Invoke-RestMethod -Uri $swUrl -Method Put -Headers $headers -Body $bytesSw
Write-Output "Torneo SWORDFISH subido a Supabase: $resSw"

$indexLocal = Get-Content 'dist\web_results\index.json' -Raw
$bytes = [System.Text.Encoding]::UTF8.GetBytes($indexLocal)
$res = Invoke-RestMethod -Uri $url -Method Put -Headers $headers -Body $bytes
Write-Output "Indice Supabase actualizado: $res"
