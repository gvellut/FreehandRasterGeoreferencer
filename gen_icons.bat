convert -size 24x24 xc:pink -gravity Center \( -density 288 -size 96x96 xc:none -fill '#ff0000' -font "Consolas"  -pointsize 14  -annotate 0 'AD' -resize 25% -fuzz 10% -trim \) -composite +repage iconAdd.png
convert -size 24x24 xc:pink -gravity Center \( -density 288 -size 96x96 xc:none -fill '#ff0000' -font "Consolas"  -pointsize 14  -annotate 0 'FRE' -resize 25% -fuzz 10% -trim \) -composite +repage icon.png
convert -size 24x24 xc:brown4 -gravity Center \( -density 288 -size 96x96 xc:none -fill 'gray88' -font "Consolas"  -pointsize 14  -annotate 0 'ADJ' -resize 25% -fuzz 3% -trim \) -composite +repage iconAdjust.png
convert -size 24x24 xc:aquamarine3 -gravity Center \( -density 288 -size 96x96 xc:none -fill 'DeepPink' -font "Consolas"  -pointsize 14  -annotate 0 '2P' -resize 25% -fuzz 10% -trim \) -composite +repage icon2Points.png
convert -size 24x24 xc:GreenYellow -gravity Center \( -density 288 -size 96x96 xc:none -fill 'red' -font "Consolas"  -pointsize 14  -annotate 0 '!!' -resize 25% -fuzz 1% -trim \) -composite +repage iconExport.png
convert -size 24x24 xc:LightGreen -gravity Center \( -density 288 -size 96x96 xc:none -fill 'tomato' -font "Consolas"  -pointsize 14  -annotate 0 'MO' -resize 25% -fuzz 1% -trim \) -composite +repage iconMove.png
convert -size 24x24 xc:purple -gravity Center \( -density 288 -size 96x96 xc:none -fill 'DarkOrange' -font "Consolas"  -pointsize 14  -annotate 0 'RO' -resize 25% -fuzz 10% -trim \) -composite +repage iconRotate.png
convert -size 24x24 xc:yellow -gravity Center \( -density 288 -size 96x96 xc:none -fill 'green' -font "Consolas"  -pointsize 14  -annotate 0 'SC' -resize 25% -fuzz 10% -trim \) -composite +repage iconScale.png
convert -size 24x24 xc:white -gravity Center \( -density 288 -size 96x96 xc:none -fill 'black' -font "Consolas"  -pointsize 14  -annotate 0 'T-' -resize 25% -fuzz 10% -trim \) -composite +repage iconTransparencyDecrease.png
convert -size 24x24 xc:black -gravity Center \( -density 288 -size 96x96 xc:none -fill 'white' -font "Consolas"  -pointsize 14  -annotate 0 'T+' -resize 25% -fuzz 10% -trim \) -composite +repage iconTransparencyIncrease.png
convert -size 24x24 xc:orange -gravity Center \( -density 288 -size 96x96 xc:none -fill 'purple' -font "Consolas"  -pointsize 14  -annotate 0 'N' -resize 25% -fuzz 10% -trim \) -composite +repage iconSelectNorth.png

