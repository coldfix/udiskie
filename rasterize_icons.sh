#! /usr/bin/env bash

# rasterize file input_dir output_dir size
# Rasterizes a given svg file using convert and scales it appropriately
function rasterize {
    local file=$1
    local input_dir=$2
    local output_dir=$3
    local size=$4
    echo "${output_dir}${file}.png"
    convert -background none $input_dir/$file.svg -resize $sizex$size $output_dir/$file.png
}


# rasterize_all input_dir output_dir size
# Rasterize all svg images in directory
function rasterize_all {
    local input_dir=$1
    local output_dir=$2
    local size=$3
    for image in $(ls ${input_dir}*.svg)
    do
        mkdir -p $output_dir
        rasterize $(basename $image .svg) $input_dir $output_dir $size
    done
}


# Loop over images and sizes
base_dir=icons/
input_dir=$base_dir/scalable/actions/
for size in 16
do
    rasterize_all $input_dir ${base_dir}${size}x${size}/actions/ $size
done
