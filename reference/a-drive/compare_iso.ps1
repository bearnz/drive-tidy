$iso = 'A:\Downloads\Jak II Renegade.iso'
$ref = 'N:\.emu\active\jak2\data\iso_data\jak2'
$img = Mount-DiskImage -ImagePath $iso -Access ReadOnly -PassThru
try {
  $root = (Get-Volume -DiskImage $img).DriveLetter + ':\'
  "Mounted at $root"
  $isoFiles = Get-ChildItem $root -Recurse -File
  $refFiles = Get-ChildItem $ref -Recurse -File
  "ISO files: $($isoFiles.Count)  extracted files: $($refFiles.Count)"
  $same = 0; $diff = @(); $missing = @()
  foreach ($f in $isoFiles) {
    $rel = $f.FullName.Substring($root.Length)
    $other = Join-Path $ref $rel
    if (-not (Test-Path -LiteralPath $other)) { $missing += $rel; continue }
    if ((Get-FileHash -LiteralPath $f.FullName).Hash -eq (Get-FileHash -LiteralPath $other).Hash) { $same++ } else { $diff += $rel }
  }
  "Identical: $same"
  "Different: $($diff.Count)"; $diff | Select-Object -First 20
  "In ISO but not extracted: $($missing.Count)"; $missing | Select-Object -First 20
  "Extracted but not in ISO:"; $refFiles | ForEach-Object { $_.FullName.Substring($ref.Length + 1) } |
    Where-Object { -not (Test-Path -LiteralPath (Join-Path $root $_)) }
} finally {
  Dismount-DiskImage -ImagePath $iso | Out-Null
  "Dismounted"
}
