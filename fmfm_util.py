#!/usr/bin/env python3

import sqlite3
import os
import sys
import shutil
import glob
from functools import partial

from settings import *
from tools import register_file, refresh_entry, remove_entry

# ---- SETTINGS ---- #
database_path = "data/data.db"
inbox = "inbox"


# ---- COMMON ---- #
def get_db():
    DB = sqlite3.connect(DATABASE_PATH)
    DB.row_factory = sqlite3.Row
    return DB


DB = get_db()


# ---- FUNCTIONS ---- #
# ---- IMPORTER ---- #
def importer(dummy):
    print(f"Files in {inbox} will be imported")
    os.makedirs(f"{inbox}", exist_ok=True)
    files = []
    for ext in ALLOWED_EXT_MIMETYPE.values():
        files.extend(glob.glob(f"{inbox}/*.{ext}"))

    for g in files:
        print()
        print(f"Process for {g}")
        try:
            new_number = register_file(g, database=DB)
        except OSError as e:
            print(str(e))
            print("Check if the DB is (not) used by other user.")
            break
        except KeyError as e:
            # Duplicate found.
            print(str(e))
            print(f"{g} moved into _duplicate folder.")
            os.makedirs(f"{inbox}/_duplicate", exist_ok=True)
            shutil.move(g, f"{inbox}/_duplicate")
            continue
        except sqlite3.Error as e:
            # This case the situation is so bad.
            print("DATABASE FAILURE", e)
            break

        refresh_entry(
            new_number, DB, extract_title=True
        )  # At first title is extracted.

        print(f"{g} moved into _finished folder.")
        os.makedirs(f"{inbox}/_finished", exist_ok=True)
        try:
            shutil.move(g, f"{inbox}/_finished")
        except shutil.Error:
            print("Something nasty! please check the filename.")

        print(f"Successfully uploaded for {g} as {new_number}")

    print("Finished!")


# ---- REMOVER ---- #
def remover(book_ids):
    print("specify book ID to be removed")
    print("script.py remove 1 2 3 4")

    for n in book_ids:
        print(f"Removing number {n}")
        try:
            remove_entry(int(n), DB)
        except IndexError:
            print(f"Err: Number {n} is not found in the database.")
        except Exception as e:
            print(f"Err: Unknown Error! {e}")

    print("Finished!")


# ---- METADATA UPDATER ---- #
def updater(book_ids, extract_title=False):
    print("specify book ID to be update metadata")
    print("script.py update 1 2 3 4")
    if extract_title:
        print("The title of book is replaced using the book's metadata.")

    for n in book_ids:
        print(f"Updating number {n}")
        try:
            refresh_entry(int(n), DB, extract_title=extract_title)
        except IndexError:
            print(f"Err: Number {n} is not found in the database.")
        except Exception as e:
            print(f"Err: Unknown Error! {e}")

    print("Finished!")


# ---- MAIN ---- #
functions = {
    "import": importer,
    "remove": remover,
    "update": updater,
    "update_title": partial(updater, extract_title=True),
}

try:
    function = sys.argv[1]
    functions[function](sys.argv[2:])
except IndexError:
    print(f'Please specify command: {" or ".join(functions.keys())}')
except KeyError:
    print(
        f'{function} is not supported. {" or ".join(functions.keys())} are supported commands.'
    )
