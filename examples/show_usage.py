#!/usr/bin/python3

import btrfs
import sys

if len(sys.argv) < 2:
    print("Usage: {} <mountpoint>".format(sys.argv[0]))
    sys.exit(1)

fs = btrfs.FileSystem(sys.argv[1])

for device in fs.devices():
    print(device)

for chunk in fs.chunks():
    print(fs.block_group(chunk.vaddr, chunk.length))
    print("    " + str(chunk))
    for stripe in chunk.stripes:
        print("        " + str(stripe))
