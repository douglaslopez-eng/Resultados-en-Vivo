$url = "https://kfcmhlsuoufvlyizqljm.supabase.co/storage/v1/object/public/atletismo-web/indice_competencias.json?v=" + [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
$res = Invoke-RestMethod -Uri $url -Method Get
$res | ConvertTo-Json -Depth 3
