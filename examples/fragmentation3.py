#!/usr/bin/python3

import btrfs
import heatmap
import math
import sys

if len(sys.argv) < 2:
    print("Usage: {} <mountpoint>".format(sys.argv[0]))
    sys.exit(1)

fs = btrfs.FileSystem(sys.argv[1])

block_groups = []
print("Loading block group objects...", file=sys.stderr)
for chunk in fs.chunks():#min_vaddr=808087191552, max_vaddr=808087191552):
    if chunk.type != btrfs.BLOCK_GROUP_DATA:
        continue
    try:
        block_groups.append(fs.block_group(chunk.vaddr, chunk.length))
    except IndexError:
        continue

print("Sorting block group objects by metadata page transid...", file=sys.stderr)
block_groups_by_transid = sorted(block_groups, key=lambda block_group: block_group.transid)

print("Using free space tree to examine free space fragmentation...", file=sys.stderr)

for block_group in block_groups_by_transid:
    if block_group.used_pct > 95:
        continue
    min_vaddr = block_group.vaddr
    max_vaddr = block_group.vaddr + block_group.length - 1

    log2_bg_length = math.log2(block_group.length)
    half_width = (log2_bg_length - 11) / 2
    shift = (log2_bg_length + 11) / 2

    score = 0
    if block_group.used != block_group.length:
        for free_space_extent in fs.free_space_extents(min_vaddr, max_vaddr):
            bad = ((1 - abs((math.log2(free_space_extent.length) - shift) / half_width))
                   * free_space_extent.length)
            print("{} {}".format(free_space_extent.length, bad))
            score += bad
        score = (score / (block_group.length - block_group.used)) * 100
    grid = heatmap.walk_extents(fs, [block_group], size=9, verbose=-1)
    png_filename = "png/{:06d}-{}-{}-{}.png".format(
        int(score),
        block_group.transid,
        block_group.used_pct,
        block_group.vaddr,
    )
    print(png_filename, file=sys.stderr)
    grid.write_png(png_filename)
print('', file=sys.stderr)
