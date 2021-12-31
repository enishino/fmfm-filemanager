#!/usr/bin/env python3

import sqlite3
import glob
import os
import shutil
import hashlib

from settings import *
from server import refresh_entry
from tools import zipcat, pdf2img, pdf2ngram

import poppler
from PIL import Image, ImageOps

database_path='data/data.db'
documents='static/documents'
thumbnails='static/thumbnails'
config = {'UPLOAD_FOLDER': documents, 'THUMBNAIL_FOLDER': thumbnails}
inbox ='inbox'

os.makedirs(f'{inbox}', exist_ok=True)

# Cropped from server.py; REFACT
def get_db():
    DB = sqlite3.connect(database_path)
    DB.row_factory = sqlite3.Row
    return DB

# *** REFACT *** just a wrapper for using function in server.py
def flash(*args):
    print(args)

# Parse all files in inbox
# (This is really similar to upload function in server and need to be merged...)
for g in glob.glob(f'{inbox}/*.*'):
    print(f'Process for {g}')
    cursor = get_db().cursor()

    bname = os.path.basename(g)
    prefix, suffix = os.path.splitext(bname)
    if suffix[1:] not in ALLOWED_EXTENSIONS:
        print(f'{g} is not the target')
        continue

    title = prefix
    filetype = suffix[1:]

    cursor.execute("select max(number) from books")
    try:
        num_max = int(cursor.fetchone()[0]) 
    except TypeError: 
        num_max = 0
    new_number = num_max + 1

    new_file_real = f'{documents}/{new_number}.{filetype}'

    if os.path.exists(new_file_real) or os.path.isfile(new_file_real):
        print(f'{new_file_real} exists in the {documents} folder.')
        continue

    # Calculate MD5
    with open(g, "rb") as f:
        hash_md5 = hashlib.md5(f.read()).hexdigest()
        cursor.execute("select * from books where md5 = ?", (hash_md5,))
        data_same_md5 = cursor.fetchall()

    # Collision!
    if len(data_same_md5) != 0:
        collision_no = ", ".join(
            [
                f"{dict(d)['number']}: {dict(d)['title']}"
                for d in data_same_md5
            ]
        )
        print(
            f"The same file (No. {collision_no}) exists in the DB"
        )
        os.makedirs(f'{inbox}/_duplicate', exist_ok=True)
        shutil.move(g, f'{inbox}/_duplicate')
        continue

    shutil.copyfile(g, new_file_real)

    try:
        # Yes this is OK so I'll insert entry into DB
        cursor.execute(
            "insert into books (number, title, filetype, md5, tags) values (?, ?, ?, ?, ?)",
            (new_number, title, filetype, hash_md5, ""),
        )
    except sqlite3.Error as e:
        os.remove(new_file_real)  # Clean up the file
        cursor.connection.rollback() # Get back the original DB
        print(f"SQL Error:{e}")
        break

    # Finally commit
    cursor.connection.commit()
    os.makedirs(f'{inbox}/_finished', exist_ok=True)
    shutil.move(g, f'{inbox}/_finished')

    refresh_entry(new_number)
    print(f"Successfully uploaded for {g} as {new_number}")
