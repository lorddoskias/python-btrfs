#!/usr/bin/python3

from collections import namedtuple
import btrfs
import os
import sys
import argparse


base_fmt_string = "file offset: {:^15d}-{:^15d} Disk: {:^15d}-{:^15d} => btrfs: 0x{:<8x} ours: "
match_fmt_string = "{}"
unmatch_fmt_string = "0x{:<8x}"

parser = argparse.ArgumentParser("Description print the checksums for a range")
parser.add_argument("filepath")
args = parser.parse_args()

if not os.path.isfile(args.filepath):
    print("{} is not a filename!".format(args.filepath))
    sys.exit(1)

inum = os.stat(args.filepath).st_ino
fd = os.open(args.filepath, os.O_RDONLY)


def get_file_extents(inode):

    tree, _ = btrfs.ioctl.ino_lookup(fd, objectid=inode)
    min_key = btrfs.ctree.Key(inode, btrfs.ctree.EXTENT_DATA_KEY, 0)
    max_key = btrfs.ctree.Key(inode + 1, btrfs.ctree.EXTENT_DATA_KEY, 0) - 1
    found_extents = []
    print("args.filepath {} tree {} inum {} ".format(args.filepath, tree, inum))
    # get the extents
    for header, data in btrfs.ioctl.search_v2(fd, tree, min_key, max_key):
        if header.type == btrfs.ctree.EXTENT_DATA_KEY:
            data_extent = btrfs.ctree.FileExtentItem(header, data)
            if data_extent.type != btrfs.ctree.FILE_EXTENT_INLINE and data_extent.disk_bytenr != 0: #skip holes
                found_extents.append(data_extent)

    return found_extents


def file_csum(f, offset):
    f.seek(offset)
    return btrfs.crc32c.crc32c_data(f.read(4096))


def print_csums(extents):

    csum_items = set()
    with open(args.filepath, "rb") as f:
        for extent in extents:
            extent_start = extent.disk_bytenr
            extent_end = extent_start + extent.disk_num_bytes
            # count of checksums for this extent
            extent_csums = (extent_end - extent_start) // 4096

            for header, data in btrfs.ioctl.search_v2(
                    fd, btrfs.ctree.CSUM_TREE_OBJECTID, buf_size=16 * 1024 * 1024):
                # how many checksums are in this item
                checksum_count = header.len // 4
                # The range checksums in this item cover
                checksum_start = header.offset
                checksum_end = checksum_start + (checksum_count * 4096)

                if extent_start >= checksum_start and extent_end <= checksum_end and extent_csums > 0:
                    if checksum_start not in csum_items:
                        print("objectid={} offset={} item size={}".format(
                            btrfs.ctree.key_objectid_str(header.objectid, header.type),
                            header.offset, header.len))
                        csum_items.add(checksum_start)
                    # how far in this checksum item do we begin. First we find
                    # how many 4kb blocks in are we
                    checksum_offset = ((extent_start - checksum_start) // 4096)
                    checksum_count -= checksum_offset
                    # Then we convert to bytes, each checksum is 4bytes (u32)
                    checksum_offset *= 4

                    for i in range(extent_csums):
                        csum_start_pos = checksum_offset + i * 4
                        checksum_range_start = extent_start + i * 4096
                        checksum_file_range = extent.logical_offset + i * 4096
                        checksum = int.from_bytes(data[csum_start_pos:csum_start_pos + 4], "little")
                        our_checksum = file_csum(f, checksum_file_range)
                        if checksum != our_checksum:
                            fmt_string = base_fmt_string + unmatch_fmt_string
                        else:
                            fmt_string = base_fmt_string + match_fmt_string
                            our_checksum = "MATCH"
                        print(
                            fmt_string.format(
                                checksum_file_range,
                                checksum_file_range + 4096,
                                checksum_range_start,
                                checksum_range_start + 4096,
                                checksum, our_checksum))

                    if checksum_count > extent_csums:
                        extent_csums -= extent_csums
                    else:
                        extent_csums -= checksum_count


extents = get_file_extents(inum)
print_csums(extents)

os.close(fd)
