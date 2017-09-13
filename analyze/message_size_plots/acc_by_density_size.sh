#!/usr/bin/env bash

# Accumulate many tracefiles in a single file

densities=( "1.00" "1.41" "2.00" "2.83" )
sizes=( 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 )
dir=$1
result=$2
interval=$3
ext=$4

for density in "${densities[@]}"; do
    mkdir -p ${result}/density-${density}

    for size in "${sizes[@]}"; do
        cat ${dir}/${size}-${density}-*-${interval}/len${ext} > ${result}/density-${density}/${size}
    done
done
exit 0