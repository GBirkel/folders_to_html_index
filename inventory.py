#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# sd_inventory.py - scan through the paths given in the configuration,
# and build an inventory of all files encountered.
# Merge it with the current inventory and then generate an HTML page that
# can be used in a browser to explore the inventory.
# Garrett Birkel
# Version 0.1
#
# LICENSE
#
# This software is provided 'as-is', without any express or implied
# warranty.  In no event will the author be held liable for any damages
# arising from the use of this software.
#
# Permission is granted to anyone to use this software for any purpose,
# including commercial applications, and to alter it and redistribute it
# freely, subject to the following restrictions:
#
# 1. The origin of this software must not be misrepresented; you must not
#    claim that you wrote the original software. If you use this software
#    in a product, an acknowledgment in the product documentation would be
#    appreciated but is not required.
# 2. Altered source versions must be plainly marked as such, and must not be
#    misrepresented as being the original software.
# 3. This notice may not be removed or altered from any source distribution.
#
# Copyright (c) 2025 Garrett Birkel

import argparse, os, re, sys, random
import subprocess
from datetime import *
from common_utils import *
from file_database import *
import json


def take_inventory(verbose=False):

    config = read_config()
    if config is None:
        print('Error reading your config.xml file!')
        sys.exit(2)

    conn = None
    cur = None

    # create a database connection
    database_file = os.path.join(config['installpath'], 'inventory.db')
    conn = connect_to_local_db(database_file, verbose)
    if not conn:
        print("Database could not be opened")
        os._exit(os.EX_IOERR)
    create_tables_if_missing(conn, verbose)
    cur = conn.cursor()

    scan_start_time = calendar.timegm(datetime.now(timezone.utc).utctimetuple())
    print("Scan begin time: %s" % (pretty_datetime(scan_start_time)))
    status = get_status_or_defaults(cur, scan_start_time)

    card_paths = [os.path.normpath(s.strip()) for s in config['paths']]

    found_card_paths = []
    for p in card_paths:
        if os.path.isdir(p):
            found_card_paths.append(p)

    if len(found_card_paths) < 1:
        print("No card paths are mounted.")
        finish_with_database(conn, cur)
        os._exit(os.EX_UNAVAILABLE)

    chosen_path = found_card_paths[0]
    print("First found path: " + chosen_path)

    card_record = get_card_by_pathname(cur, chosen_path)
    if card_record is None:
        print("First time seeing this path.")

        f = os.open(chosen_path, os.O_RDONLY)
        s = os.fstat(f)
        new_card = {
            "id": None,
            "name": os.path.basename(chosen_path),
            "pathname": chosen_path,
            "size": s.st_size,
            "file_count": 0,
            "creation_time": int(s.st_mtime)
        }
        insert_or_update_card(cur, verbose, new_card)
        card_record = get_card_by_pathname(cur, chosen_path)

    if card_record is None:
        print("Could not fetch newly created card record?")
        print(card_record)
        finish_with_database(conn, cur)
        os._exit(os.EX_IOERR)

    card_id = card_record['id']
    clear_files_and_folders_for_card(cur, verbose, card_id)

    print("\nPerforming initial folder scan of %s:" % (chosen_path))
    folders, files = get_folders_and_files(chosen_path)
    print("  %s folders, %s files" % (len(folders), len(files)))
    content_size = 0
    for f in files:
        s = f.stat()
        record = {
            "id": None,
            "card_id": card_id,
            "folder_id": 0,
            "name": f.name,
            "pathname": f.path,
            "size": s.st_size,
            "last_modified_time": int(s.st_mtime)
        }
        insert_or_update_file(cur, verbose, record)
        content_size += s.st_size

    for f in folders:
        s = f.stat()
        record = {
            "id": None,
            "card_id": card_id,
            "parent_folder_id": 0,
            "name": f.name,
            "pathname": f.path,
            "file_count": 0,
            "file_count_recursive": 0,
            "content_size": 0,
            "content_size_recursive": 0,
            "last_modified_time": int(s.st_mtime),
            "scanned_contents": 0
        }
        insert_or_update_folder(cur, verbose, record)

    print("Main folder file content size %.2fmb" % (content_size / (1000 * 1000)))

    print("\nPerforming progressive folder scan of %s:" % (chosen_path))

    total_content_size = 0
    folders_processed_count = 0
    hit_stop_limit = False

    folder_record = get_one_unscanned_folder(cur)
    while (folder_record is not None) and (not hit_stop_limit):

        print("\nExamining %s:" % (folder_record['pathname']))
        folders, files = get_folders_and_files(folder_record['pathname'])
        print("  %s folders, %s files" % (len(folders), len(files)))
        content_size = 0
        for f in files:
            s = f.stat()
            record = {
                "id": None,
                "card_id": card_id,
                "folder_id": folder_record['id'],
                "name": f.name,
                "pathname": f.path,
                "size": s.st_size,
                "last_modified_time": int(s.st_mtime)
            }
            insert_or_update_file(cur, verbose, record)
            content_size += s.st_size

        for f in folders:
            s = f.stat()
            record = {
                "id": None,
                "card_id": card_id,
                "parent_folder_id": folder_record['id'],
                "name": f.name,
                "pathname": f.path,
                "file_count": 0,
                "file_count_recursive": 0,
                "content_size": 0,
                "content_size_recursive": 0,
                "last_modified_time": int(s.st_mtime),
                "scanned_contents": 0
            }
            insert_or_update_folder(cur, verbose, record)

        folder_record['file_count'] = len(files)
        folder_record['content_size'] = content_size
        folder_record['scanned_contents'] = 1

        insert_or_update_folder(cur, verbose, folder_record)

        total_content_size += content_size

        folders_processed_count += 1

        folder_record = get_one_unscanned_folder(cur)

    print("\nExporting to JSON")

    all_cards = get_all_cards(cur)
    all_folders = get_all_folders(cur, verbose)
    all_files = get_all_files(cur)

    with open(os.path.join('browser', 'card_data.js'), 'w', encoding='utf-8') as f:
        f.write('// This file is generated automatically by inventory.py.\n\n')
        f.write('const card_data = ')
        json.dump(all_cards, f, indent=2)
        f.write(';\n')

    with open(os.path.join('browser', 'folder_data.js'), 'w', encoding='utf-8') as f:
        f.write('// This file is generated automatically by inventory.py.\n\n')
        f.write('const folder_data = ')
        json.dump(all_folders, f, indent=2)
        f.write(';\n')

    with open(os.path.join('browser', 'file_data.js'), 'w', encoding='utf-8') as f:
        f.write('// This file is generated automatically by inventory.py.\n\n')
        f.write('const file_data = ')
        json.dump(all_files, f, indent=2)
        f.write(';\n')

    finish_with_database(conn, cur)
    os._exit(0)


if __name__ == "__main__":
    args = argparse.ArgumentParser(description="Choose an image from the library and display it")
    args.add_argument("--quiet", "-q", action='store_false', dest='verbose',
                      help="reduce log output")
    args = args.parse_args()

    take_inventory(
        verbose=args.verbose,
    )
