param([string[]]$Paths)
# Sends each path to the Recycle Bin, one at a time, and stops if the bin didn't grow by the item's size.
Add-Type -AssemblyName Microsoft.VisualBasic
# The shell reports recycled folders as 0 bytes, so measure the bin's folder on disk instead.
$binDir = "C:\`$Recycle.Bin\" + ([System.Security.Principal.WindowsIdentity]::GetCurrent()).User.Value
function BinBytesOnC { (Get-ChildItem -LiteralPath $binDir -File -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum }

foreach ($p in $Paths) {
    if (-not (Test-Path -LiteralPath $p)) { "SKIP (missing): $p"; continue }
    $item = Get-Item -LiteralPath $p -Force
    $files = if ($item.PSIsContainer) { Get-ChildItem -LiteralPath $p -File -Recurse -Force -ErrorAction SilentlyContinue } else { $item }
    $size = ($files | Measure-Object Length -Sum).Sum
    $before = BinBytesOnC
    try {
        if ($item.PSIsContainer) {
            [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory($p, 'OnlyErrorDialogs', 'SendToRecycleBin')
        } else {
            [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($p, 'OnlyErrorDialogs', 'SendToRecycleBin')
        }
    } catch { "ERROR: $p -> $($_.Exception.Message)"; break }
    Start-Sleep -Milliseconds 500
    $after = BinBytesOnC
    $grew = $after - $before
    $still = Test-Path -LiteralPath $p
    "{0,8:N2} GB  bin +{1,6:N2} GB  gone={2}  {3}" -f ($size/1GB), ($grew/1GB), (-not $still), $p
    if ($size -gt 10MB -and $grew -lt $size * 0.9) { "STOP: bin did not grow by the item's size, check before continuing"; break }
}
"C: free now: {0:N1} GB; C: bin holds {1:N2} GB" -f ((Get-PSDrive C).Free/1GB), ((BinBytesOnC)/1GB)
