Add-Type -AssemblyName Microsoft.VisualBasic
$ErrorActionPreference = 'Stop'

# src, dst, binSourceAfterVerify
$jobs = @(
  @('A:\Downloads\The.Lord.of.the.Rings.The.Fellowship.of.the.Ring.2001.EXTENDED.1080p.BluRay.10bit.HEVC.6CH.MkvCage.ws.mkv',
    'N:\.plex\Movies\The Lord of the Rings - The Fellowship of the Ring (2001) {edition-Extended}\The Lord of the Rings - The Fellowship of the Ring (2001) {edition-Extended}.mkv', $true),
  @('A:\Downloads\Rick and Morty - S04E01 - Edge of Tomorty - Rick Die Rickpeat.mkv',
    'N:\.plex\TV\Rick and Morty\Season 4\Rick and Morty S04E01 - Edge of Tomorty Rick Die Rickpeat.mkv', $true)
)
$wed = 'N:\Videos\Josh And Monicas Wedding'
foreach ($n in '20251010_144440.mp4', '20251010_144440.mp4.sfk', 'Josh And Monicas Wedding 1080p.mp4') {
  $jobs += ,@("A:\$n", "$wed\$n", $false)
}
Get-ChildItem 'A:\.vid' -File | ForEach-Object { $jobs += ,@($_.FullName, "$wed\Vegas projects\$($_.Name)", $false) }

foreach ($j in $jobs) {
  $src, $dst, $bin = $j
  if (Test-Path -LiteralPath $dst) { "SKIP exists: $dst"; continue }
  New-Item -ItemType Directory -Force -Path (Split-Path -LiteralPath $dst) | Out-Null
  Copy-Item -LiteralPath $src -Destination $dst
  $h1 = (Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash
  $h2 = (Get-FileHash -LiteralPath $dst -Algorithm SHA256).Hash
  if ($h1 -ne $h2) { "HASH MISMATCH: $src -> $dst"; continue }
  if ($bin) {
    [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($src, 'OnlyErrorDialogs', 'SendToRecycleBin')
    "MOVED (hash ok, source binned): $dst"
  } else {
    "COPIED (hash ok, source kept): $dst"
  }
}
"DONE"
