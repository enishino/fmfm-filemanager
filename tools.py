#!/usr/bin/env python3

import os
import io
import logging
import re
import unicodedata
import hashlib
import zipfile

import sqlite3
from contextlib import closing

import poppler
from poppler import PageRenderer
from poppler import RenderHint
from PIL import Image

from settings import *

# Image generation
def pdf2img(filename, page=0, dpi=192):
    pdf = poppler.load_from_file(filename)
    if page >= pdf.pages:
        raise IndexError
    renderer = PageRenderer()
    renderer.set_render_hint(RenderHint.text_antialiasing, True)
    renderer.set_render_hint(RenderHint.antialiasing, True)
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

def num_sort(k):
    folname = os.path.dirname(k)
    basename = os.path.basename(k)
    nosuf, suffix = os.path.splitext(basename)
    numero = ".".join(nosuf.split("."))
    try:
        return int(numero)
    except ValueError:
        return str(numero)


def zipcat(filename, page=None):
    ### *** REFACT ***  split len and get ###
    with zipfile.ZipFile(filename) as archive:
        entries = archive.namelist()
        image_srcs = [
            i
            for i in entries
            if i.lower().endswith(IMG_SUFFIX) and not archive.getinfo(i).is_dir()
        ]
        image_srcs = sorted(image_srcs)#, key=num_sort)
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
