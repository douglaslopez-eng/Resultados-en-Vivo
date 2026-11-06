$html = (Invoke-WebRequest -Uri "https://atletismopro-resultados.pages.dev/?nocache=$(Get-Random)").Content
if ($html.Contains("SUPABASE_BASE_URL")) {
    $idx = $html.IndexOf("SUPABASE_BASE_URL")
    $sub = $html.Substring($idx, 150)
    Write-Output "Found: $sub"
} else {
    Write-Output "SUPABASE_BASE_URL NOT FOUND"
}
