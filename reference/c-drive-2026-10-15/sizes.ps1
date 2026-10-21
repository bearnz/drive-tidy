param([string[]]$Roots)
foreach ($root in $Roots) {
  if (-not (Test-Path $root)) { continue }
  "=== $root ==="
  Get-ChildItem -LiteralPath $root -Force -Directory -ErrorAction SilentlyContinue |
    Where-Object { -not ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) } |
    ForEach-Object {
      $s = (Get-ChildItem -LiteralPath $_.FullName -Recurse -Force -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
      [pscustomobject]@{GB=[math]::Round($s/1GB,2); Path=$_.FullName}
    } | Where-Object GB -ge 0.5 | Sort-Object GB -Descending | Format-Table -AutoSize | Out-String -Width 200
  $files = Get-ChildItem -LiteralPath $root -Force -File -ErrorAction SilentlyContinue | Where-Object Length -gt 500MB
  $files | ForEach-Object { "{0,8:N2} GB  {1}" -f ($_.Length/1GB), $_.FullName }
}
