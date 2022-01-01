#!/usr/bin/env python3

import os
import re
import unicodedata
import hashlib
import zipfile
import sqlite3
import shutil

import poppler
from poppler import PageRenderer
from poppler import RenderHint
from PIL import Image, ImageOps

from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage

from settings import *

# Image generation
def pdf2img(filename, page=0, dpi=192, antialias=True):
    pdf = poppler.load_from_file(filename)
    if page >= pdf.pages:
        raise IndexError
    renderer = PageRenderer()
    renderer.set_render_hint(RenderHint.text_antialiasing, antialias)
    renderer.set_render_hint(RenderHint.antialiasing, antialias)
    image = renderer.render_page(pdf.create_page(page), xres=dpi, yres=dpi)
    pil_image = Image.frombytes(
        "RGBA",
        (image.width, image.height),
        image.data,
        "raw",
        str(image.format),
    )
    pil_image = pil_image.convert("RGB")
    return pil_image


def zipcat(filename, page=None):
    ### *** REFACT ***  split len and get ###
    with zipfile.ZipFile(filename) as archive:
        entries = archive.namelist()
        image_srcs = [
            i
            for i in entries
            if i.lower().endswith(IMG_SUFFIX) and not archive.getinfo(i).is_dir()
        ]
        image_srcs = sorted(image_srcs)
        if page == None:
            return len(image_srcs)

        with archive.open(image_srcs[page]) as file:
            img = Image.open(file)
            imgmode = img.mode
            imgtype = img.format
            img = img.copy()
            return img, imgtype, imgmode


# Text indexing
non2b_chars = r"[\u3041-\u3096\u30A1-\u30FA々〇〻\u3400-\u9FFF\uF900-\uFAFF]|[\uD840-\uD87F\uDC00-\uDFFF\u3000-\u303F]"


def pdf2ngram(filename, gram_n=2):
    text_per_page = pdf2txt(filename)
    ngram_per_page = []
    for t in text_per_page:
        txt_ary = re.split("[\s\-\/\;]", t)
        if max([len(a) for a in txt_ary]) > 40 or re.match(non2b_chars, t):
            # Contains non-western language
            ngram_per_page.append(n_gram(t, gram_n=gram_n))
        else:
            # The text is already tokenized (european lang.).
            ngram_per_page.append(t)
    return ngram_per_page

def pdf2txt(pdf_path):
    pdf = poppler.load_from_file(pdf_path)
    pages = []
    for i in range(pdf.pages):
        # Extraction
        t = pdf.create_page(i).text()
        # Join to one line
        t = "".join(t.splitlines()).strip()
        # Remove extra whitespaces
        t = re.sub("[ 　\t,\"'●■□一]+", " ", t)
        t = re.sub(". . ", "", t)
        # Remove errornous whitespaces in Japanese OCR
        for _ in range(3):
            t = re.sub(f"({non2b_chars}+)[ \t　]({non2b_chars}+)", "\\1\\2", t)
        # Remove ligartures (fi, fl and so on)
        t = unicodedata.normalize("NFKC", t)
        # Remove errornous dots
        t = re.sub("[\.,\"'●■□~=ー\−][\.,\"'●■□~=ー\−]+", "", t)
        # Finally append
        pages.append(t)
    return pages


def n_gram(txt, gram_n=2):
    return " ".join([txt[n : n + gram_n] for n in range(len(txt) - gram_n + 1)])

def n_gram_to_txt(txt):
    txt_ary = re.split("[\s\-\/\;]", txt)
    if max([len(a) for a in txt_ary]) < 3:
        # seems n-grammed
        recovered = txt_ary[0][:-1] + ''.join([a[-1] for a in txt_ary if len(a) != 0])
        return recovered
    else:
        # maybe Non n-grammed
        return txt

def register_file(a_file, DB):
    if type(a_file) == FileStorage:
        file_data = a_file
        filename = secure_filename(a_file.filename)
    elif type(a_file) == str:
        file_data = None
        filename = os.path.basename(a_file)

    # Get current maximum number of data
    cursor = DB.cursor()
    cursor.execute("select max(number) from books")
    try:
        num_max = int(cursor.fetchone()[0])  # **** REFACT ****
    except TypeError:  # This mean the DB has no entry
        num_max = 0
    new_number = num_max + 1

    # Get name and suffix
    filename = os.path.basename(filename)
    if not "." in filename:
        filename = f"{new_number}.{filename}"  # Japanese filenames makes this failure
    basename, suffix = os.path.splitext(filename)

    filetype = suffix.replace(".", "")
    if filetype in ["", None]:
        raise TypeError(f"No suffix. Something wrong with filename ({filename})?")

    # Rename the file into a sequential number
    new_filename = str(new_number) + suffix.lower()
    new_file_real = os.path.join(UPLOADDIR_PATH, new_filename)

    # Already existed?
    if os.path.exists(new_file_real) or os.path.isfile(new_file_real):
        raise OSError(f"Collision on uploading (file {new_number} exists). Please try again.")

    # Seems OK, Go ahead
    try:
        if file_data:
            # Saving uploaded file
            a_file.save(new_file_real)
        else:
            # Copy original to upload folder
            shutil.copyfile(a_file, new_file_real)

        # Calculate MD5
        with open(new_file_real, "rb") as f:
            hash_md5 = hashlib.md5(f.read()).hexdigest()
            cursor.execute("select * from books where md5 = ?", (hash_md5,))
            data_same_md5 = cursor.fetchall()

        # Collision! which file is the problem?
        if len(data_same_md5) != 0:
            os.remove(new_file_real)  # Clean up the file
            collision_no = ", ".join(
                [
                    f"{dict(d)['number']} {dict(d)['title']}"
                    for d in data_same_md5
                ]
            )
            raise KeyError(
                f"The same file (No. {collision_no}) exists in the DB"
            )

        # Yes this is OK so I'll insert entry into DB
        cursor.execute(
            "insert into books (number, title, filetype, md5, tags) values (?, ?, ?, ?, ?)",
            (new_number, basename, filetype, hash_md5, ""),
        )

    except sqlite3.Error as e:
        os.remove(new_file_real)  # Clean up the file
        cursor.connection.rollback()  # Cancel the modification
        raise sqlite3.Error(f"SQL Error:{e}", "failed")

    # Finally commit
    cursor.connection.commit()
    return new_number

def refresh_entry(number, DB):
    cursor = DB.cursor()
    cursor.execute("select * from books where number = ?", (number,))
    entry = cursor.fetchone()

    if entry == None:
        raise IndexError

    filetype = entry["filetype"]
    filename = str(number) + f".{filetype}"
    file_thumbnail = str(number) + ".jpg"
    file_real = os.path.join(UPLOADDIR_PATH, filename)
    thumb_real = os.path.join(THUMBDIR_PATH, file_thumbnail)

    if filetype == "pdf":
        # Number of pages
        pagenum = poppler.load_from_file(file_real).pages
        cursor.execute(
            "update books set pagenum = ? where number = ?", (pagenum, number)
        )

        # Generate thumbnail
        thumbnail = pdf2img(file_real)
        thumbnail = thumbnail.convert("RGB")
        thumbnail = ImageOps.contain(thumbnail, (400, 400))
        thumbnail.save(thumb_real, "JPEG")

        # Generate text index
        page_ngram = pdf2ngram(file_real)
        index_data = tuple((number, p, t) for p, t in enumerate(page_ngram))
        cursor.execute("delete from fts where number = ?", (number,))
        cursor.executemany(
            "insert into fts (number, page, ngram) values (?, ?, ?)", index_data
        )

    if filetype == "zip":
        pagenum = zipcat(file_real)
        cursor.execute(
            "update books set pagenum = ? where number = ?", (pagenum, number)
        )
        thumbnail, imgtype, imgmode = zipcat(file_real, page=0)
        thumbnail = thumbnail.convert("RGB")
        thumbnail = ImageOps.contain(thumbnail, (400, 400))
        thumbnail.save(thumb_real, "JPEG")

    # Spread view: 1=True, 0=False
    if entry["spread"] == None:
        cursor.execute("update books set spread = ? where number = ?", (True, number))

    # L2R view: 1=True, 0=False
    if entry["r2l"] == None:
        cursor.execute("update books set r2l = ? where number = ?", (False, number))

    # Hiding: 1=True, 0=False
    if entry["hide"] == None:
        cursor.execute("update books set hide = ? where number = ?", (False, number))

    # Update MD5 hash
    with open(file_real, "rb") as f:
        hash_md5 = hashlib.md5(f.read()).hexdigest()
    cursor.execute("update books set md5 = ? where number = ?", (hash_md5, number))

    # Finally commit
    cursor.connection.commit()
