#!/usr/bin/env python3

import sqlite3
import os
import sys
from werkzeug.exceptions import NotFound

from settings import *
from tools import register_file, refresh_entry, remove_entry

database_path='data/data.db'
inbox ='inbox'

os.makedirs(f'{inbox}', exist_ok=True)

print("specify book ID to be removed")
print("script.py 1 2 3 4")

def get_db():
    DB = sqlite3.connect(DATABASE_PATH)
    DB.row_factory = sqlite3.Row
    return DB

DB = get_db()
for n in sys.argv[1:]:
    print(f'Removing number {n}')
    try:
        remove_entry(int(n), DB)
    except NotFound:
        print(f'Number {n} is not found in the database.')
    except Exception as e:
        print(f'Unknown Error! {e}')

print('Finished!')
