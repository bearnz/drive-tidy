param([string]$Drive, [string]$Out)
# Fast full file listing via robocopy /L: "<bytes>\t<fullpath>" per line
robocopy "$Drive`:\" "C:\__nodest__" /L /S /XJ /BYTES /FP /NC /NDL /NJH /NJS /R:0 /W:0 /XD "System Volume Information" |
  ForEach-Object { $t = $_.Trim(); if ($t) { $t -replace '^(\d+)\s+', '$1|' } } |
  Set-Content -LiteralPath $Out -Encoding UTF8
"done $Drive"
