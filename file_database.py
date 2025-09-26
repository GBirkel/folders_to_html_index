#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# file_database.py - functions for managing a collection of files.
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

from datetime import *
import calendar
import sqlite3
from sqlite3 import Error
from xml.sax import saxutils


def connect_to_local_db(db_file, verbose):
    """ create a database connection to the SQLite database
        specified by the db_file
    :param db_file: database file
    :param verbose: whether we are verbose logging
    :return: Connection object or None
    """
    conn = None
    if verbose:
        print('Opening local database: %s' % db_file)
    try:
        conn = sqlite3.connect(db_file)
    except Error as e:
        print(e)

    return conn


def create_tables_if_missing(conn, verbose):
    """ create needed database tables if missing
    :param conn: database connection
    :param verbose: whether we are verbose logging
    """
    if verbose:
        print('Creating tables if needed')

    conn.execute("""
        CREATE TABLE IF NOT EXISTS status (
            last_run INTEGER NOT NULL
        )""")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS card (
            id INTEGER PRIMARY KEY NOT NULL,
            size INTEGER NOT NULL,
            name TEXT NOT NULL,
            creation_time INTEGER NOT NULL,
            pathname TEXT NOT NULL DEFAULT "",
            file_count INTEGER NOT NULL DEFAULT 0,
            CONSTRAINT card_pathname_unique UNIQUE (pathname)
        )""")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS folder (
            id INTEGER PRIMARY KEY NOT NULL,
            card_id INTEGER NOT NULL,
            parent_folder_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            pathname TEXT NOT NULL,
            file_count INTEGER NOT NULL,
            file_count_recursive INTEGER NOT NULL,
            content_size INTEGER NOT NULL,
            content_size_recursive INTEGER NOT NULL,
            last_modified_time INTEGER NOT NULL,
            first_seen_time INTEGER NOT NULL,
            scanned_contents INTEGER NOT NULL,
            CONSTRAINT parent_folder_id_name_unique UNIQUE (card_id, parent_folder_id, name)
        )""")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS file (
            id INTEGER PRIMARY KEY NOT NULL,
            card_id INTEGER NOT NULL,
            folder_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            pathname TEXT NOT NULL,
            size INTEGER NOT NULL,
            last_modified_time INTEGER NOT NULL,
            CONSTRAINT folder_id_name_unique UNIQUE (card_id, folder_id, name)
        )""")

    conn.execute("""
        CREATE INDEX IF NOT EXISTS file_folder_id
            ON "file" (folder_id);
        """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS file_card_id
            ON "file" (card_id);
        """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS folder_card_id
            ON "folder" (card_id);
        """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS folder_parent_folder_id
            ON "folder" (parent_folder_id);
        """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS folder_content_size
            ON "folder" (content_size);
        """)



def get_status_or_defaults(cur, last_run):
    """ get values from the current status record, or create a new one if missing
    :param cur: database cursor
    :param last_run: default last_run value
    """
    data = {'last_run': last_run}
    cur.execute("SELECT last_run FROM status")
    row = cur.fetchone()
    if not row:
        cur.execute("INSERT INTO status (last_run) VALUES (:last_run)", data)
    else:
        last_run = row[0]
    status = {"last_run": last_run}
    return status


def set_status(cur, status):
    """ set values in the current status record
    :param cur: database cursor
    :param status: sync status record
    """
    cur.execute("""UPDATE status SET
        (last_run)
        VALUES (?)""",
        (status['last_run']))


def get_files_in_folder(cur, card_id, folder_id):
    """ fetch an array of file records in the given card and folder id
    :param cur: database cursor
    :param card_id: card id
    :param folder_id: folder id
    """
    params = { "card_id": int(card_id), "folder_id": int(folder_id) }
    cur.execute("""SELECT
            id, card_id, folder_id, name, pathname,
            size, last_modified_time
        FROM file WHERE card_id = :card_id AND folder_id = :folder_id""", (params))
    rows = cur.fetchall()
    records = []
    for row in rows:
        record = {
            "id": row[0],
            "card_id": row[1],
            "folder_id": row[2],
            "name": row[3],
            "pathname": row[4],
            "size": row[5],
            "last_modified_time": row[6],
        }
        records.append(record)
    return records


def get_all_files(cur):
    """ fetch an array of all file records (this could be quite a big array)
    :param cur: database cursor
    """
    cur.execute("""SELECT
            id, card_id, folder_id, name, pathname,
            size, last_modified_time
        FROM file""")
    rows = cur.fetchall()
    records = []
    for row in rows:
        record = {
            "id": row[0],
            "card_id": row[1],
            "folder_id": row[2],
            "name": row[3],
            "pathname": row[4],
            "size": row[5],
            "last_modified_time": row[6],
        }
        records.append(record)
    return records


def clear_files_and_folders_for_card(cur, verbose, card_id):
    """ remove all file and folder records for the given card id
    :param cur: database cursor
    :param verbose: whether we are verbose logging
    :param card_id: card id
    :return: True if the folder did not already exist
    """
    data = {'card_id': card_id}
    if verbose:
        print('Clearing folders and files for card id %s' % (card_id))
    cur.execute("DELETE FROM file WHERE card_id = :card_id", data)
    cur.execute("DELETE FROM folder WHERE card_id = :card_id", data)
    return True


def insert_or_update_folder(cur, verbose, record):
    """ insert a new folder or update an existing one with a matching parent folder id and name
    :param cur: database cursor
    :param verbose: whether we are verbose logging
    :param record: folder record
    :return: True if the folder did not already exist
    """

    if record['id'] == None:
        cur.execute("SELECT id FROM folder WHERE card_id = :card_id AND parent_folder_id = :parent_folder_id AND name = :name", record)
    else:
        cur.execute("SELECT id FROM folder WHERE id = :id", record)

    row = cur.fetchone()
    if not row:
        if verbose:
            print('Adding new folder record %s' % (record['pathname']))
        record['first_seen_time'] = calendar.timegm(datetime.now(timezone.utc).utctimetuple())
        cur.execute("""
            INSERT INTO folder (
                card_id,
                parent_folder_id,
                name,
                pathname,
                file_count, file_count_recursive, content_size, content_size_recursive,
                last_modified_time, first_seen_time, scanned_contents
            ) VALUES (
                :card_id,
                :parent_folder_id,
                :name,
                :pathname,
                :file_count, :file_count_recursive, :content_size, :content_size_recursive,
                :last_modified_time, :first_seen_time, :scanned_contents
            )""", record)
        return True
    else:
        record['id'] = row[0]
        if verbose:
            print('Updating existing folder %s' % (record['pathname']))
        cur.execute("""
            UPDATE folder SET
                file_count = :file_count,
                file_count_recursive = :file_count_recursive,
                content_size = :content_size,
                content_size_recursive = :content_size_recursive,
                last_modified_time = :last_modified_time,
                scanned_contents = :scanned_contents
            WHERE id = :id""", record)
        return False


def insert_or_update_file(cur, verbose, record):
    """ insert a new file or update an existing one with a matching folder id and name
    :param cur: database cursor
    :param verbose: whether we are verbose logging
    :param record: file record
    :return: True if the file did not already exist
    """

    if record['id'] == None:
        cur.execute("SELECT id FROM file WHERE card_id = :card_id AND folder_id = :folder_id AND name = :name", record)
    else:
        cur.execute("SELECT id FROM file WHERE id = :id", record)

    row = cur.fetchone()
    if not row:
        if verbose:
            print('Adding new file record %s' % (record['pathname']))
        cur.execute("""
            INSERT INTO file (
                card_id,
                folder_id,
                name, pathname, size,
                last_modified_time
            ) VALUES (
                :card_id,
                :folder_id,
                :name, :pathname, :size,
                :last_modified_time
            )""", record)
        return True
    else:
        record['id'] = row[0]
        if verbose:
            print('Updating existing file %s' % (record['pathname']))
        cur.execute("""
            UPDATE file SET
                card_id = :card_id,
                size = :size,
                last_modified_time = :last_modified_time
            WHERE id = :id""", record)
        return False


def get_one_unscanned_folder(cur):
    """ get an arbitrary folder that does not yet have
    its contents scanned (scanned_contents is 0)
    :param cur: database cursor
    :param verbose: whether we are verbose logging
    :return: An dictionary
    """
    cur.execute("""SELECT
            id, card_id, parent_folder_id, name, pathname,
            file_count, file_count_recursive, content_size, content_size_recursive,
            last_modified_time, first_seen_time, scanned_contents
        FROM folder WHERE scanned_contents = 0
        ORDER BY last_modified_time LIMIT 1""")
    row = cur.fetchone()
    if not row:
        return None
    record = {
        "id": row[0],
        "card_id": row[1],
        "parent_folder_id": row[2],
        "name": row[3],
        "pathname": row[4],
        "file_count": row[5],
        "file_count_recursive": row[6],
        "content_size": row[7],
        "content_size_recursive": row[8],
        "last_modified_time": row[9],
        "first_seen_time": row[10],
        "scanned_contents": row[11],
    }
    return record


def get_all_folders(cur, verbose):
    """ get all known folders
    :param cur: database cursor
    :param verbose: whether we are verbose logging
    :return: An dictionary
    """
    if verbose:
        print('Fetching all folders from database')
    cur.execute("""SELECT
            id, card_id, parent_folder_id, name, pathname,
            file_count, file_count_recursive, content_size, content_size_recursive,
            last_modified_time, first_seen_time, scanned_contents
        FROM folder""")
    rows = cur.fetchall()
    records = []
    for row in rows:
        record = {
            "id": row[0],
            "card_id": row[1],
            "parent_folder_id": row[2],
            "name": row[3],
            "pathname": row[4],
            "file_count": row[5],
            "file_count_recursive": row[6],
            "content_size": row[7],
            "content_size_recursive": row[8],
            "last_modified_time": row[9],
            "first_seen_time": row[10],
            "scanned_contents": row[11],
        }
        records.append(record)
    return records


def get_all_cards(cur):
    """ fetch an array of all card records
    :param cur: database cursor
    """
    cur.execute("""SELECT
            id, name, pathname,
            size, file_count, creation_time
        FROM card""")
    rows = cur.fetchall()
    records = []
    for row in rows:
        record = {
            "id": row[0],
            "name": row[1],
            "pathname": row[2],
            "size": row[3],
            "file_count": row[4],
            "creation_time": row[5]
        }
        records.append(record)
    return records


def get_card_by_pathname(cur, pathname):
    """ fetch a card by its source path
    :param cur: database cursor
    :param pathname: source path
    """
    data = {'pathname': pathname}
    cur.execute("""SELECT
            id, name, pathname, size, file_count, creation_time
        FROM card WHERE pathname = :pathname""", data)
    row = cur.fetchone()
    if not row:
        return None

    record = {
        "id": row[0],
        "name": row[1],
        "pathname": row[2],
        "size": row[3],
        "file_count": row[4],
        "creation_time": row[5]
    }
    return record


def insert_or_update_card(cur, verbose, record):
    """ insert a new card or update an existing one with a matching folder id and name
    :param cur: database cursor
    :param verbose: whether we are verbose logging
    :param record: card record
    :return: True if the card did not already exist
    """

    if record['id'] is not None:
        cur.execute("SELECT id FROM card WHERE id = :id", record)
        row = cur.fetchone()
        if not row:
            if verbose:
                print('Card record with id %s not found, cannot update.' % (record['id']))
            return False
        else:
            if verbose:
                print('Updating existing card %s' % (record['pathname']))
            cur.execute("""
                UPDATE card SET
                    name = :name,
                    pathname = :pathname,
                    size = :size,
                    file_count = :file_count,
                    creation_time = :creation_time
                WHERE id = :id""", record)
            return False
    else:
        if verbose:
            print('Adding new card record %s' % (record['pathname']))
        cur.execute("""
            INSERT INTO card (
                name,
                pathname,
                size,
                file_count,
                creation_time
            ) VALUES (
                :name,
                :pathname,
                :size,
                :file_count,
                :creation_time
            )""", record)
        return True


def finish_with_database(conn, cur):
    """ commit and close the cursor and database
    :param conn: database connection
    :param cur: database cursor
    """
    conn.commit()
    conn.close()