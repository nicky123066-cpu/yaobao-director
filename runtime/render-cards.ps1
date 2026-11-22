param([Parameter(Mandatory=$true)][string]$RequestPath)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$cardRequest = Get-Content -LiteralPath $RequestPath -Raw -Encoding UTF8 | ConvertFrom-Json
function Solid([string]$hex) { return New-Object System.Drawing.SolidBrush([System.Drawing.ColorTranslator]::FromHtml($hex)) }
foreach ($card in $cardRequest.cards) {
  $w = [int]$card.width; $h = [int]$card.height
  $bitmap = New-Object System.Drawing.Bitmap($w, $h)
  $g = [System.Drawing.Graphics]::FromImage($bitmap)
  $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
  $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
  $owned = New-Object System.Collections.Generic.List[System.IDisposable]
  try {
    if ($card.transparent) { $g.Clear([System.Drawing.Color]::Transparent) } elseif ($card.image -and (Test-Path -LiteralPath $card.image) -and -not ([string]$card.image).EndsWith('.svg')) {
      $source = [System.Drawing.Image]::FromFile([string]$card.image)
      try {
        $scale = [Math]::Max($w / $source.Width, $h / $source.Height)
        $dw = [int]($source.Width * $scale); $dh = [int]($source.Height * $scale)
        $g.DrawImage($source, [int](($w-$dw)/2), [int](($h-$dh)/2), $dw, $dh)
      } finally { $source.Dispose() }
    } else {
      $palettes = @(@('#10222d','#52656a','#d9bc86'),@('#102a32','#3e777b','#e4a77f'),@('#1c3030','#7e9a89','#dbe3bd'),@('#1e2030','#716376','#ddc5a4'),@('#262b31','#8d897a','#f2d9ad'),@('#142d3b','#6c899c','#d7c9b8'))
      $p = $palettes[([int]$card.variant % 6)]
      $bounds = New-Object System.Drawing.Rectangle(0,0,$w,$h)
      $gradient = New-Object System.Drawing.Drawing2D.LinearGradientBrush($bounds, [System.Drawing.ColorTranslator]::FromHtml($p[0]), [System.Drawing.ColorTranslator]::FromHtml($p[1]), 90.0)
      $owned.Add($gradient); $g.FillRectangle($gradient,$bounds)
      $moon=Solid $p[2];$owned.Add($moon)
      $g.FillEllipse($moon,[single]($w*.65),[single]($h*.16),[single]($w*.19),[single]($w*.19))
      $dark=Solid $p[0];$owned.Add($dark)
      $street=Solid $p[1];$owned.Add($street)
      $streetPoints=[System.Drawing.PointF[]]@((New-Object System.Drawing.PointF([single]($w*.59),[single]($h*.45))),(New-Object System.Drawing.PointF([single]($w*.2),[single]$h)),(New-Object System.Drawing.PointF([single]($w*.9),[single]$h)))
      $g.FillPolygon($street,$streetPoints)
      $random=New-Object System.Random(72+[int]$card.variant)
      for($layer=0;$layer -lt 3;$layer++) {
        for($i=0;$i -lt 7;$i++) {
          $x=[single](($i-1)*$w*.22+$layer*$w*.065)
          $y=[single]($h*(.4+$layer*.13)+$random.Next(-35,30))
          $bw=[single]($w*.22);$roof=[single]($h*.04)
          $g.FillRectangle($dark,$x,$y,$bw,[single]($h-$y))
          $points=[System.Drawing.PointF[]]@((New-Object System.Drawing.PointF([single]($x-$bw*.13),[single]$y)),(New-Object System.Drawing.PointF([single]($x+$bw*.5),[single]($y-$roof))),(New-Object System.Drawing.PointF([single]($x+$bw*1.13),[single]$y)),(New-Object System.Drawing.PointF([single]($x+$bw),[single]($y+$roof*.2))),(New-Object System.Drawing.PointF([single]$x,[single]($y+$roof*.2))))
          $g.FillPolygon($dark,$points)
          for($j=1;$j -le 3;$j++) {$g.FillRectangle($moon,[single]($x+$j*$bw*.21),[single]($y+$h*.045),[single]($bw*.08),[single]($h*.027))}
        }
      }
      $px=[single]($w*.6);$py=[single]($h*.72)
      $g.FillEllipse($dark,[single]($px-$w*.017),[single]($py-$h*.04),[single]($w*.034),[single]($h*.035))
      $robe=[System.Drawing.PointF[]]@((New-Object System.Drawing.PointF([single]($px-$w*.016),[single]($py-$h*.012))),(New-Object System.Drawing.PointF([single]($px+$w*.016),[single]($py-$h*.012))),(New-Object System.Drawing.PointF([single]($px+$w*.048),[single]($py+$h*.14))),(New-Object System.Drawing.PointF([single]($px-$w*.046),[single]($py+$h*.14))))
      $g.FillPolygon($dark,$robe)
      $umbrella=Solid '#aa9782';$owned.Add($umbrella)
      $g.FillPie($umbrella,[single]($px-$w*.1),[single]($py-$h*.105),[single]($w*.27),[single]($h*.105),180.0,180.0)
      $pen=New-Object System.Drawing.Pen([System.Drawing.ColorTranslator]::FromHtml('#b7a383'),[single]2);$owned.Add($pen)
      $g.DrawLine($pen,[single]($px+$w*.035),[single]($py-$h*.055),[single]($px+$w*.035),[single]($py+$h*.07))
      $rain=New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(29,220,225,222),[single]1);$owned.Add($rain)
      for($r=0;$r -lt 150;$r++) {$rx=$random.Next(0,$w);$ry=$random.Next(0,$h);$g.DrawLine($rain,[single]$rx,[single]$ry,[single]($rx-5),[single]($ry+25))}
    }
    if ($card.compose) {
      $rect=New-Object System.Drawing.Rectangle(0,[int]($h*.52),$w,[int]($h*.48))
      $shade=New-Object System.Drawing.Drawing2D.LinearGradientBrush($rect,[System.Drawing.Color]::FromArgb(0,5,10,17),[System.Drawing.Color]::FromArgb(245,5,10,17),90.0);$owned.Add($shade);$g.FillRectangle($shade,$rect)
      $white=Solid '#f4ebdd';$owned.Add($white)
      $small=New-Object System.Drawing.Font('Microsoft YaHei',[single]($w/52),[System.Drawing.FontStyle]::Regular,[System.Drawing.GraphicsUnit]::Pixel);$owned.Add($small)
      $font=New-Object System.Drawing.Font('Microsoft YaHei',[single]($w/27),[System.Drawing.FontStyle]::Regular,[System.Drawing.GraphicsUnit]::Pixel);$owned.Add($font)
      $g.DrawString([string]$card.title,$small,$white,[single]($w*.055),[single]($h*.038))
      $g.DrawString([string]$card.mark,$small,$white,[single]($w*.055),[single]($h*.065))
      $wrapped=New-Object System.Collections.Generic.List[string];$line=''
      foreach($character in ([string]$card.caption).ToCharArray()) {
        $next=$line+$character
        if($g.MeasureString($next,$font).Width -gt $w*.86 -and $line.Length -gt 0) {$wrapped.Add($line);$line=[string]$character} else {$line=$next}
      }
      if($line){$wrapped.Add($line)}
      $lh=[single]($w*.055);$top=[single]($h*.9-$wrapped.Count*$lh)
      for($l=0;$l -lt $wrapped.Count;$l++){$g.DrawString($wrapped[$l],$font,$white,[single]($w*.07),[single]($top+$l*$lh))}
      $g.DrawString([string]$card.label,$small,$white,[single]($w*.055),[single]($h*.955))
    }
    $bitmap.Save([string]$card.output,[System.Drawing.Imaging.ImageFormat]::Png)
  } finally {
    foreach($resource in $owned){$resource.Dispose()}
    $g.Dispose();$bitmap.Dispose()
  }
}
