param([switch]$Apply)
# Builds the approved cleanup list for E: and, with -Apply, sends each item to the Recycle Bin.
Add-Type -AssemblyName Microsoft.VisualBasic
$FS = [Microsoft.VisualBasic.FileIO.FileSystem]
$UI = [Microsoft.VisualBasic.FileIO.UIOption]::OnlyErrorDialogs
$RB = [Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin
$common = 'E:\steam\steamapps\common'

function Size($p) {
    if (Test-Path -LiteralPath $p -PathType Leaf) { return (Get-Item -LiteralPath $p -Force).Length }
    $m = Get-ChildItem -LiteralPath $p -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum
    [int64]$m.Sum
}

$items = New-Object System.Collections.Generic.List[object]
function Add($cat, $path) { $items.Add([pscustomobject]@{Cat=$cat; Path=$path; Bytes=(Size $path); Newest=$null}) }

# 1. Game folders in common\ that no Steam manifest claims (re-checked now, not from the earlier scan)
$installdirs = Get-ChildItem 'E:\steam\steamapps\appmanifest_*.acf' | ForEach-Object {
    if ((Get-Content $_.FullName -Raw) -match '"installdir"\s+"([^"]+)"') { $matches[1] } }
$orphans = Get-ChildItem $common -Directory | Where-Object { $installdirs -notcontains $_.Name }
$orphans | ForEach-Object { Add 'leftover game folder' $_.FullName }

# 2. Old Windows leftovers at the root of E:
'E:\WINDOWS', 'E:\ProgramData', 'E:\MSOCache', 'E:\msdownld.tmp' | Where-Object { Test-Path -LiteralPath $_ } |
    ForEach-Object { Add 'old windows leftover' $_ }

# 3. Logs and crash dumps inside installed games (orphan folders are already covered above)
$orphanPaths = $orphans.FullName
Get-ChildItem $common -Recurse -File -Force -ErrorAction SilentlyContinue |
    Where-Object { ($_.Extension -in '.log', '.dmp', '.mdmp' -or $_.Name -like 'output_log*.txt') } |
    Where-Object { $f = $_.FullName; -not ($orphanPaths | Where-Object { $f.StartsWith($_ + '\') }) } |
    ForEach-Object { Add 'log / crash dump' $_.FullName }

# 4. Empty Steam temp / workshop / shader folders for apps not installed in this library
$ids = Get-ChildItem 'E:\steam\steamapps\appmanifest_*.acf' | ForEach-Object { $_.BaseName -replace 'appmanifest_', '' }
foreach ($d in 'E:\steam\steamapps\temp', 'E:\steam\steamapps\workshop\content', 'E:\steam\steamapps\shadercache') {
    if (Test-Path $d) {
        Get-ChildItem $d -Directory | Where-Object { $ids -notcontains $_.Name } |
            Where-Object { (Size $_.FullName) -eq 0 } | ForEach-Object { Add 'empty steam folder' $_.FullName }
    }
}

foreach ($i in $items) {
    $n = if (Test-Path -LiteralPath $i.Path -PathType Container) {
        Get-ChildItem -LiteralPath $i.Path -Recurse -File -Force -ErrorAction SilentlyContinue | Sort-Object LastWriteTime | Select-Object -Last 1
    } else { Get-Item -LiteralPath $i.Path -Force }
    $i.Newest = if ($n) { $n.LastWriteTime.ToString('yyyy-MM-dd') } else { '-' }
}

$items | Group-Object Cat | ForEach-Object {
    '== {0}: {1} items, {2:N1} MB' -f $_.Name, $_.Count, (($_.Group | Measure-Object Bytes -Sum).Sum / 1MB)
    $_.Group | ForEach-Object { '  {0,9:N1} KB  newest {1}  {2}' -f ($_.Bytes / 1KB), $_.Newest, $_.Path }
}
'TOTAL {0:N1} MB' -f (($items | Measure-Object Bytes -Sum).Sum / 1MB)

if ($Apply) {
    '== applying'
    foreach ($i in $items) {
        try {
            if (Test-Path -LiteralPath $i.Path -PathType Container) { $FS::DeleteDirectory($i.Path, $UI, $RB) }
            else { $FS::DeleteFile($i.Path, $UI, $RB) }
            $left = Test-Path -LiteralPath $i.Path
            '{0}  {1}' -f $(if ($left) { 'STILL THERE' } else { 'recycled   ' }), $i.Path
        } catch { 'FAILED       {0}  ({1})' -f $i.Path, $_.Exception.Message }
    }
}
