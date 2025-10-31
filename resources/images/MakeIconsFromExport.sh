#!/bin/bash
# shellcheck disable=SC2046,SC2164,SC2086

# ~/Downloads/export ➜ file *
# OrcaSlicer__1024.png:             PNG image data, 1024 x 1024, 8-bit/color RGBA, non-interlaced
# OrcaSlicer__128.png:              PNG image data, 128 x 128, 8-bit/color RGBA, non-interlaced
# OrcaSlicer__16.png:               PNG image data, 16 x 16, 8-bit/color RGBA, non-interlaced
# OrcaSlicer__2048.png:             PNG image data, 2048 x 2048, 8-bit/color RGBA, non-interlaced
# OrcaSlicer__24.png:               PNG image data, 24 x 24, 8-bit/color RGBA, non-interlaced
# OrcaSlicer__256.png:              PNG image data, 256 x 256, 8-bit/color RGBA, non-interlaced
# OrcaSlicer__32.png:               PNG image data, 32 x 32, 8-bit/color RGBA, non-interlaced
# OrcaSlicer__48.png:               PNG image data, 48 x 48, 8-bit/color RGBA, non-interlaced
# OrcaSlicer__512.png:              PNG image data, 512 x 512, 8-bit/color RGBA, non-interlaced
# OrcaSlicer__64.png:               PNG image data, 64 x 64, 8-bit/color RGBA, non-interlaced
# OrcaSlicer_128px.png:             PNG image data, 128 x 128, 8-bit/color RGBA, non-interlaced
# OrcaSlicer_154_title.png:         PNG image data, 154 x 154, 8-bit/color RGBA, non-interlaced
# OrcaSlicer_154.png:               PNG image data, 154 x 154, 8-bit/color RGBA, non-interlaced
# OrcaSlicer_192px_grayscale.png:   PNG image data, 192 x 192, 8-bit/color RGBA, non-interlaced
# OrcaSlicer_192px_transparent.png: PNG image data, 192 x 192, 8-bit/color RGBA, non-interlaced
# OrcaSlicer_192px.png:             PNG image data, 192 x 192, 8-bit/color RGBA, non-interlaced
# OrcaSlicer_32px.png:              PNG image data, 32 x 32, 8-bit/color RGBA, non-interlaced
# OrcaSlicer_64.png:                PNG image data, 64 x 64, 8-bit/color RGBA, non-interlaced
# OrcaSlicer_about_dark.svg:        SVG Scalable Vector Graphics image
# OrcaSlicer_about.svg:             SVG Scalable Vector Graphics image
# OrcaSlicer_gradient_circle.svg:   SVG Scalable Vector Graphics image
# OrcaSlicer_gradient_narrow.svg:   SVG Scalable Vector Graphics image
# OrcaSlicer_gradient.svg:          SVG Scalable Vector Graphics image
# OrcaSlicer_gray.svg:              SVG Scalable Vector Graphics image
# OrcaSlicer-mac_128px.png:         PNG image data, 128 x 128, 8-bit/color RGBA, non-interlaced
# OrcaSlicer-mac_256px.png:         PNG image data, 256 x 256, 8-bit/color RGBA, non-interlaced
# OrcaSlicer.png:                   PNG image data, 154 x 154, 8-bit/color RGBA, non-interlaced
# OrcaSlicer.svg:                   SVG Scalable Vector Graphics image
# OrcaSlicerTitle.png:              PNG image data, 154 x 154, 8-bit/color RGBA, non-interlaced

# OrcaSlicer/resources/images ➜ file OrcaSlicer*
# OrcaSlicer_128px.png:             PNG image data, 128 x 128, 8-bit/color RGBA, non-interlaced
# OrcaSlicer_154_title.png:         PNG image data, 184 x 184, 8-bit/color RGBA, non-interlaced
# OrcaSlicer_154.png:               PNG image data, 154 x 154, 8-bit/color RGBA, non-interlaced
# OrcaSlicer_192px_grayscale.png:   PNG image data, 192 x 192, 8-bit/color RGBA, non-interlaced
# OrcaSlicer_192px_transparent.png: PNG image data, 192 x 192, 8-bit/color RGBA, non-interlaced
# OrcaSlicer_192px.png:             PNG image data, 192 x 192, 8-bit/color RGBA, non-interlaced
# OrcaSlicer_32px.png:              PNG image data, 32 x 32, 8-bit/color RGBA, non-interlaced
# OrcaSlicer_64.png:                PNG image data, 64 x 64, 8-bit/color RGBA, non-interlaced
# OrcaSlicer_about_dark.svg:        SVG Scalable Vector Graphics image
# OrcaSlicer_about.svg:             SVG Scalable Vector Graphics image
# OrcaSlicer_gradient_circle.svg:   SVG Scalable Vector Graphics image
# OrcaSlicer_gradient_narrow.svg:   SVG Scalable Vector Graphics image
# OrcaSlicer_gradient.svg:          SVG Scalable Vector Graphics image
# OrcaSlicer_gray.svg:              SVG Scalable Vector Graphics image
# OrcaSlicer-mac_128px.png:         PNG image data, 128 x 128, 8-bit/color RGBA, non-interlaced
# OrcaSlicer-mac_256px.ico:         MS Windows icon resource - 1 icon, 256x256 with PNG image data, 256 x 256, 8-bit/color RGBA, non-interlaced, 32 bits/pixel
# OrcaSlicer.icns:                  Mac OS X icon, 401478 bytes, "TOC " type
# OrcaSlicer.ico:                   MS Windows icon resource - 6 icons, 16x16, 32 bits/pixel, 32x32, 32 bits/pixel
# OrcaSlicer.png:                   PNG image data, 154 x 154, 8-bit/color RGBA, non-interlaced
# OrcaSlicer.svg:                   SVG Scalable Vector Graphics image
# OrcaSlicerTitle.ico:              MS Windows icon resource - 1 icon, -102x-102, 32 bits/pixel
# OrcaSlicerTitle.png:              PNG image data, 154 x 154, 8-bit/color RGBA, non-interlaced

PREFIX=OrcaSlicer

SOURCE=~/Downloads/export
BASE=~/Documents/work/OrcaSlicer
TARGET=$BASE/resources/images

rm ${TARGET}/${PREFIX}*
cp -f ${SOURCE}/* ${TARGET}/
cd ${TARGET}

ICO_SIZES=(16 24 32 48 64 128 256)
ICNS_BASE_SIZES=(16 32 64 128 256 512 1024)

cp -f ${PREFIX}_154.png   ${BASE}/resources/web/image/logo.png
cp -f ${PREFIX}__512.png  ${BASE}/resources/web/image/logo2.png

magick $(printf "${PREFIX}__%s.png " "${ICO_SIZES[@]}") -strip -alpha on "${PREFIX}.ico"

magick "${PREFIX}-mac_256px.png" -strip -alpha on "${PREFIX}-mac_256px.ico"
rm ${PREFIX}-mac_256px.png

magick "${PREFIX}Title.png" -strip -alpha on "${PREFIX}Title.ico"

mkdir ${PREFIX}.iconset
for size in "${ICNS_BASE_SIZES[@]}"; do
  cp ${PREFIX}__${size}.png      ${PREFIX}.iconset/icon_${size}x${size}.png
  cp ${PREFIX}__$((size*2)).png  ${PREFIX}.iconset/icon_${size}x${size}@2x.png
done
iconutil -c icns ${PREFIX}.iconset
rm -rf ${PREFIX}.iconset

cp -f ${PREFIX}.icns ${BASE}/resources/Icon.icns

for size in "${ICO_SIZES[@]}"; do
  rm -f ${PREFIX}__${size}.png
done

for size in "${ICNS_BASE_SIZES[@]}"; do
  rm -f ${PREFIX}__${size}.png
done
rm -f ${PREFIX}__2048.png
