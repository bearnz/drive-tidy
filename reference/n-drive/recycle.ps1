param($List, $Log)
Add-Type -AssemblyName Microsoft.VisualBasic
$fs = [Microsoft.VisualBasic.FileIO.FileSystem]
$ui = [Microsoft.VisualBasic.FileIO.UIOption]::OnlyErrorDialogs
$rb = [Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin
$out = foreach ($line in Get-Content -LiteralPath $List -Encoding UTF8) {
  $c, $p, $s, $r = $line -split "`t"
  try {
    if (Test-Path -LiteralPath $p -PathType Container) { $fs::DeleteDirectory($p, $ui, $rb) }
    elseif (Test-Path -LiteralPath $p -PathType Leaf) { $fs::DeleteFile($p, $ui, $rb) }
    else { "MISSING`t$p"; continue }
    if (Test-Path -LiteralPath $p) { "STILL-THERE`t$p" } else { "OK`t$p" }
  } catch { "ERR`t$p`t$($_.Exception.Message)" }
}
$out | Set-Content -LiteralPath $Log -Encoding UTF8
$out | ForEach-Object { ($_ -split "`t")[0] } | Group-Object | Format-Table Name, Count -AutoSize
