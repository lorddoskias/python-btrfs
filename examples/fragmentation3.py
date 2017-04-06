#!/usr/bin/python3

import btrfs
import heatmap
import math
import shutil
import sys
import time

if len(sys.argv) < 3:
    print("Usage: {} <min_score> <mountpoint>".format(sys.argv[0]))
    sys.exit(1)

min_score = int(sys.argv[1])
fs = btrfs.FileSystem(sys.argv[2])

skipped_max_usage = skipped_min_fragmented = skipped_gone = 0

for chunk in fs.chunks():
    if chunk.type != btrfs.BLOCK_GROUP_DATA:
        continue
    try:
        block_group = fs.block_group(chunk.vaddr, chunk.length)
    except IndexError:
        skipped_gone += 1
        continue
    if block_group.used_pct >= 80:
        skipped_max_usage += 1
        continue

    min_vaddr = block_group.vaddr
    max_vaddr = block_group.vaddr + block_group.length - 1

    log2_bg_length = math.log2(block_group.length)
    half_width = (log2_bg_length - 11) / 2
    shift = (log2_bg_length + 11) / 2

    score = 0
    #print("used {} length {}".format(block_group.used, block_group.length))
    if block_group.used != block_group.length:
        tree = btrfs.ctree.FREE_SPACE_TREE_OBJECTID
        min_key = btrfs.ctree.Key(min_vaddr, 0, 0)
        max_key = btrfs.ctree.Key(max_vaddr, 255, btrfs.ctree.ULLONG_MAX)
        for header, _ in btrfs.ioctl.search_v2(fs.fd, tree, min_key, max_key):
            if header.type == btrfs.ctree.FREE_SPACE_BITMAP_KEY:
                score = 1000
                break
            elif header.type == btrfs.ctree.FREE_SPACE_EXTENT_KEY:
                free_space_extent = btrfs.ctree.FreeSpaceExtent(header.objectid, header.offset)
                bad = 1 - abs((math.log2(free_space_extent.length) - shift) / half_width)
                score += bad
    if score >= min_score:
        print("skipped max_usage {} min_fragmented {} gone {}".format(
            skipped_max_usage, skipped_min_fragmented, skipped_gone))
        skipped_max_usage = skipped_min_fragmented = skipped_gone = 0

        grid = heatmap.walk_extents(fs, [block_group], size=9, verbose=-1)
        png_filename = "/srv/www/btrfs-fragmented/processed/{}-{:06d}-{}-{}.png".format(
            int(time.time()), int(score), block_group.used_pct, block_group.vaddr)
        print(png_filename)
        grid.write_png(png_filename)
        shutil.copy2(png_filename, '/srv/www/btrfs-fragmented/now.png')
        args = btrfs.ioctl.BalanceArgs(vstart=min_vaddr, vend=min_vaddr+1)
        print(btrfs.ioctl.balance_v2(fs.fd, data_args=args))
    else:
        skipped_min_fragmented += 1

