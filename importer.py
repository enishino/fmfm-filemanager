#!/usr/bin/env python3

import sqlite3
import glob
import os
import shutil
import hashlib

from settings import *
from tools import register_file, refresh_entry

database_path='data/data.db'
inbox ='inbox'

os.makedirs(f'{inbox}', exist_ok=True)

print(f'Put the documents into {inbox} folder.')
print('Then run this script to import them at once.')

def get_db():
    DB = sqlite3.connect(DATABASE_PATH)
    DB.row_factory = sqlite3.Row
    return DB

# Parse all files in inbox
files = []
for ext in ALLOWED_EXT_MIMETYPE.values():
    files.extend(glob.glob(f'{inbox}/*.{ext}'))

for g in files:
    print()
    print(f'Process for {g}')
    try:
        new_number = register_file(g, database=get_db())
    except OSError as e:
        print(str(e))
        print('Check if the DB is used by other user.')
        break
    except KeyError as e:
        # Duplicate found.
        print(str(e))
        print(f'{g} moved into _duplicate folder.')
        os.makedirs(f'{inbox}/_duplicate', exist_ok=True)
        shutil.move(g, f'{inbox}/_duplicate')
        continue
    except sqlite3.Error as e:
        # This case the situation is bad.
        print(e)
        break

    refresh_entry(new_number, get_db())

    print(f'{g} moved into _finished folder.')
    os.makedirs(f'{inbox}/_finished', exist_ok=True)
    shutil.move(g, f'{inbox}/_finished')

    print(f"Successfully uploaded for {g} as {new_number}")
else:
    print(f'No file was discovered to be imported.')
