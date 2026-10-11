# Contact sheet: tiles of the given PNGs (label under each) -> one PNG.
param([string[]]$Files, [string]$Out, [int]$Cols = 3, [int]$TileW = 520)
Add-Type -AssemblyName System.Drawing
$imgs = @(); foreach ($f in $Files) { if (Test-Path $f) { $imgs += [Drawing.Image]::FromFile($f) } }
$tiles = @(); $maxH = 0
foreach ($i in $imgs) { $h = [int]($i.Height * $TileW / $i.Width); $tiles += ,@($i, $h); if ($h -gt $maxH) { $maxH = $h } }
$rows = [math]::Ceiling($imgs.Count / $Cols); $cellH = [math]::Min($maxH, 420) + 24
$bmp = New-Object Drawing.Bitmap ($Cols * ($TileW + 8) + 8), ($rows * $cellH + 8)
$g = [Drawing.Graphics]::FromImage($bmp); $g.Clear([Drawing.Color]::FromArgb(40,40,40))
$g.InterpolationMode = 'HighQualityBicubic'
$font = New-Object Drawing.Font 'Segoe UI', 9
for ($k = 0; $k -lt $tiles.Count; $k++) {
  $x = 8 + ($k % $Cols) * ($TileW + 8); $y = 8 + [math]::Floor($k / $Cols) * $cellH
  $w = $TileW; $h = $tiles[$k][1]; if ($h -gt 420) { $w = [int]($TileW * 420 / $h); $h = 420 }
  $g.DrawImage($tiles[$k][0], $x, $y, $w, $h)
  $g.DrawString(("{0}. {1}" -f ($k + 1), [IO.Path]::GetFileNameWithoutExtension($Files[$k])), $font, [Drawing.Brushes]::White, $x, $y + $h + 2)
}
$bmp.Save($Out, [Drawing.Imaging.ImageFormat]::Png)
