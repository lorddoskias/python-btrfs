#!/usr/bin/python3

import btrfs
import math
import os
import sys

if len(sys.argv) < 2:
    print("Usage: {} <mountpoint>".format(sys.argv[0]))
    sys.exit(1)

fs = btrfs.FileSystem(sys.argv[1])

block_groups = []
print("Loading block group objects...", file=sys.stderr)
for chunk in fs.chunks():#max_vaddr=72658561531904):
    if chunk.type != btrfs.BLOCK_GROUP_DATA:
        continue
    try:
        block_group = fs.block_group(chunk.vaddr, chunk.length)
        if block_group.used_pct < 75:
            block_groups.append(block_group)
    except IndexError:
        continue

print("Sorting block group objects by usage...", file=sys.stderr)
block_groups_by_usage = sorted(block_groups, key=lambda block_group: block_group.used)

print("""#!/bin/bash
set -e
set -x
trap 'exit 0' 2
""")
for block_group in block_groups_by_usage:
    min_vaddr = block_group.vaddr
    max_vaddr = block_group.vaddr + block_group.length - 1
    total_bad = 0
    for free_space_extent in fs.free_space_extents(min_vaddr, max_vaddr):
        how_bad = 1 - ((math.log2(free_space_extent.length) - 12) * 0.075)
        if how_bad > 0:
            total_bad += how_bad
    if total_bad < 150:
        continue
    pngfile = "/root/usage-pics/{}-{}-{}-{}.png".format(
        block_group.transid, round(total_bad), block_group.used_pct, block_group.vaddr)
    print("btrfs-heatmap --blockgroup {} --size 9 -o {} /srv/backup".format(
        block_group.vaddr, pngfile))
    print("cp {} /srv/www/test/now.png".format(pngfile))
    print("btrfs balance start -dvrange={}..{} /srv/backup  # used_pct {} fragmented {}".format(
        block_group.vaddr, block_group.vaddr + 1,
        block_group.used_pct, round(total_bad)))
    print('.', file=sys.stderr, end='', flush=True)
print('', file=sys.stderr)
