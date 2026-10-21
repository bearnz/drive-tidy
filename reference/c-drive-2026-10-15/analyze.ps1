param([string]$File)
$l1=@{}; $l2=@{}; $l3=@{}; $ext=@{}; $big=New-Object System.Collections.Generic.List[object]; $special=@{}; $total=0
foreach ($line in [IO.File]::ReadLines($File)) {
  $i=$line.IndexOf('|'); if ($i -lt 1) { continue }
  $b=[double]$line.Substring(0,$i); $p=$line.Substring($i+1); $total+=$b
  $parts=$p.Split('\')
  if ($parts.Length -gt 2) { $k=$parts[0..1] -join '\'; $l1[$k]+=$b }
  if ($parts.Length -gt 3) { $k=$parts[0..2] -join '\'; $l2[$k]+=$b }
  if ($parts.Length -gt 4) { $k=$parts[0..3] -join '\'; $l3[$k]+=$b }
  $e=[IO.Path]::GetExtension($p).ToLower(); $ext[$e]+=$b
  if ($b -gt 2GB) { $big.Add([pscustomobject]@{GB=[math]::Round($b/1GB,1);Path=$p}) }
  foreach ($m in [regex]::Matches($p,'(?i)^(.*?\(node_modules|\$RECYCLE\.BIN|\.venv|venv|__pycache__|\.gradle|Library\ShaderCache|Temp|Logs|obj|bin\Debug|\.godot|crashdumps))\')) { $special[$m.Groups[1].Value]+=$b; break }
}
function Top($h,$n,$min){ $h.GetEnumerator() | Where-Object { $_.Value -ge $min } | Sort-Object Value -Descending | Select-Object -First $n | ForEach-Object { "{0,8:N1} GB  {1}" -f ($_.Value/1GB),$_.Key } }
"TOTAL listed: {0:N0} GB" -f ($total/1GB)
"--- Top-level"; Top $l1 25 1GB
"--- Level 2"; Top $l2 30 5GB
"--- Level 3"; Top $l3 30 10GB
"--- Biggest files (>2GB)"; $big | Sort-Object GB -Descending | Select-Object -First 25 | ForEach-Object { "{0,8:N1} GB  {1}" -f $_.GB,$_.Path }
"--- Extensions"; Top $ext 15 5GB
"--- Cache/build folders (grouped, >0.3GB)"; $grp=@{}; foreach($k in $special.Keys){ $grp[$k]=$special[$k] }; Top $grp 25 0.3GB
