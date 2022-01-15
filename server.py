#!/usr/bin/env python3

import os
import io
import logging
import re
import unicodedata
import hashlib
import zipfile
import socket
import requests

from flask import Flask, render_template, request, redirect, url_for, make_response
from flask import abort, flash, session, send_file, send_from_directory
from flask import g
from flask_paginate import Pagination, get_page_parameter
from werkzeug.urls import url_encode
from werkzeug.exceptions import NotFound
from werkzeug.datastructures import FileStorage

import sqlite3
from contextlib import closing

import poppler
from poppler import PageRenderer
from poppler import RenderHint
from PIL import Image, ImageOps

from tools import zipcat, pdf2img, register_file, refresh_entry
from tools import pdf2ngram, pdf2txt, n_gram, n_gram_to_txt
from settings import *


# Flask initialization
app = Flask(__name__)
app.secret_key = "fmfm"
config = {'SESSION_COOKIE_HTTPONLY': True, 'SESSION_COOKIE_SAMESITE': "Lax"}
app.config.from_mapping(config)

# Hostname (just for showing)
hostname = socket.gethostname()


# DB management
# Opening DB
def get_db():
    DB = getattr(g, "_database", None)
    if DB is None:
        DB = g._database = sqlite3.connect(DATABASE_PATH)
        DB.row_factory = sqlite3.Row
    return DB


# Closing DB
@app.teardown_appcontext
def close_connection(exception):
    DB = getattr(g, "_database", None)
    if DB is not None:
        DB.close()


# Initialization
def init_db():
    with closing(sqlite3.connect(DATABASE_PATH)) as db:
        with app.open_resource(SCHEMA_PATH, mode="r") as f:
            db.cursor().executescript(f.read())
        db.commit()


# SQlite3 Row -> Dict with error handling
def sqlresult_to_an_entry(result):
    try:
        data = dict(result)
        return data
    except TypeError:
        raise NotFound


# Mini tools
# to append queries with AND condition
@app.template_global()
def modify_query(**new_values):
    args = request.args.copy()
    for key, value in new_values.items():
        args[key] = value
    return args


# Tag cloud
@app.template_global()
def taglist():
    cursor = get_db().cursor()
    cursor.execute("select tags from books")
    all_tag = [t[0] for t in cursor.fetchall() if t[0] != ""]  # *** REFACT ***
    tags = set(" ".join(all_tag).strip().split(" "))
    return sorted(tags)


# PIL Image -> Image file
def send_pil_image(pil_img, imgtype="JPEG", imgmode="RGB", quality=100, shrink=False, caching=True):
    pil_img = pil_img.convert(imgmode)
    if shrink: # REFACT consider splitting
        imgtype = "JPEG"
        pil_img = pil_img.convert("RGB")
        quality = 90

    img_io = io.BytesIO()
    pil_img.save(img_io, imgtype, quality=quality)
    img_io.seek(0)
    mimetypes = {"PNG": "image/png", "JPEG": "image/jpeg", "BMP": "image/bmp"}
    response = make_response(send_file(img_io, mimetype=mimetypes[imgtype]))
    if caching:
        response.headers['Cache-Control'] = 'max-age=3000'
    return response


# Text -> excerpted text (in search result)
def excerpt(txt, start, end, length):
    is_asian = any([True for c in txt if unicodedata.east_asian_width(c) in "FWA"])
    if is_asian:
        length = length // 2
    start = 0 if start < length else start - length
    end = -1 if len(txt) - end < length else end + length
    return txt[start:end]


# Sorting method table
sort_methods = {'title_asc': ('title', 'asc'), 'title_desc': ('title', 'desc'),
                'number_asc': ('number', 'asc'), 'number_desc': ('number', 'desc')}

# Each Page
# Main
@app.route("/")
def index():
    # In this gridview just tag search is enabled
    tag = request.args.get("tag", type=str, default="")
    sort_by = request.args.get("sort_by", type=str, default="number_desc")
    if sort_by in sort_methods.keys():
        sort_col, sort_meth = sort_methods[sort_by]
    else:
        flash('Failure on selecting sorting method', 'failure')
        sort_col, sort_meth = 'number', 'desc' # as default.

    cursor = get_db().cursor()
    if tag == "":
        # No query
        sql_query = f"""select * from books order by {sort_col} {sort_meth}"""
    else:
        # Tag search
        sql_query = f"""select * from books where tags like :tag order by {sort_col} {sort_meth}"""

    # Run SQL query
    cursor.execute(
        sql_query,
        {
            "tag": "%" + tag + "%",
        },
    )
    data = cursor.fetchall()

    # Page position control
    page = request.args.get(get_page_parameter(), type=int, default=1)
    per_page = request.args.get("per_page", type=int, default=PER_PAGE_ENTRY)

    # Extraction of data
    start_at = per_page * (page - 1)
    end_at = per_page * (page)
    data_in_page = data[start_at:end_at]

    # Split result into pages
    pagination = Pagination(
        page=page, total=len(data), per_page=per_page, css_framework="bootstrap5"
    )

    return render_template(
        "list.html",
        title=f"FMFM: Fast Minimal File Manager (at {hostname})",
        rows=data_in_page,
        pagination=pagination,
        tag=tag,
        sort_by=sort_by,
    )


@app.route("/search")
def search():
    cursor = get_db().cursor()

    query = request.args.get("query", type=str, default="")
    tag = request.args.get("tag", type=str, default="")
    if query == "":
        return redirect(url_for("index", tag=tag))

    # *** REFACT *** Dirty!
    # Clean up the query
    query = query.replace("\u3000", " ")  # full-width space
    query = re.sub(" ([\&\+\(\)\*\\\#]) ", r"\1", query)  # Care for orphan symbols
    # (i) For western languages
    query_quoted = " ".join([f'"{q}"' for q in query.split(" ")])
    # (ii) for languages without delimiter
    ngram_ary = [f'"{n_gram(q)}"' if len(q) > 1 else q for q in query.split(" ")]
    query_ngram = "(" + " ".join(ngram_ary) + ")"
    # (iii) (i) and (ii) are merged
    query_merged = query_quoted + " OR " + query_ngram

    if query_merged.strip() == "":
        flash(f"No meaningful query generated for {query}", "failed")
        return redirect(url_for("index", tag=tag))

    # *** TODO: sorting not working now *** #
    sort_by = request.args.get("sort_by", type=str, default="title_asc")
    if sort_by in sort_methods:
        sort_col, sort_meth = sort_methods[sort_by]
    else:
        flash('Failure on selecting sorting method', 'failure')
        sort_col, sort_meth = 'title', 'asc'

    # Query for titles
    if tag == "":
        # without tag
        sql_query = f"""select * from books where number in (
                select distinct number from fts where ngram match :textquery order by bm25(fts))
                or title like :title order by {sort_col} {sort_meth}"""
    else:
        # with tag
        sql_query = f"""select * from books where number in (
                select distinct number from fts where ngram match :textquery order by bm25(fts))
                and tags like :tag or title like :title order by {sort_col} {sort_meth}"""

    # Run SQL query
    cursor.execute(
        sql_query,
        {
            "textquery": query_merged,
            "title": "%" + query + "%",
            "tag": "%" + tag + "%",  # Any tag matches...
        },
    )
    data = cursor.fetchall()
    # Title information of each book
    title_hits = {d["number"]: d["title"] for d in data}
    tag_hits = {d["number"]: d["tags"] for d in data}
    # Reformat into a dict, with each book as index
    excerpt_per_book = {}
    # Filter by title exist and specified tag
    filtered_by_tag = {}

    # Query for full text
    cursor.execute(
        "select * from fts where ngram match :textquery order by bm25(fts)",
        {
            "textquery": query_merged,
        },
    )
    fts_data = [dict(d) for d in cursor.fetchall()]

    if len(fts_data):
        for d in fts_data:
            # Show matched phrase in the FTS
            orig_txt = n_gram_to_txt(d["ngram"])
            hit_excerpt = ""
            for q in query.split(" "):
                match = re.search(q, orig_txt, re.IGNORECASE)
                if match == None:
                    continue
                begin, end = match.start(), match.end()
                hit_excerpt += "..." + excerpt(orig_txt, begin, end, 40)
            d["excerpt"] = hit_excerpt + "..."

        for d in fts_data:
            if d["excerpt"] == "..." or d["number"] not in title_hits.keys():
                # Omit false match
                continue
            if d["number"] in excerpt_per_book.keys():
                excerpt_per_book[d["number"]].update({d["page"]: d["excerpt"]})
            else:
                excerpt_per_book[d["number"]] = {d["page"]: d["excerpt"]}

        # Including document title
        for k, v in title_hits.items():
            if query.lower() in v.lower():
                if k in excerpt_per_book.keys():
                    excerpt_per_book[k].update({0: "[Document Title matches]"})
                else:
                    excerpt_per_book[k] = {0: "[Document Title matches]"}

    # Page position control
    page = request.args.get(get_page_parameter(), type=int, default=1)
    per_page = request.args.get("per_page", type=int, default=PER_PAGE_SEARCH)

    # Extraction of data how can i... first set is ok but 2nd...
    start_at = per_page * (page - 1)
    end_at = per_page * (page)
    data_in_page = dict(list(excerpt_per_book.items())[start_at:end_at])

    # Split result into pages
    pagination = Pagination(
        page=page,
        total=len(excerpt_per_book),
        per_page=per_page,
        css_framework="bootstrap5",
    )

    return render_template(
        "search.html",
        title=f"Search result for {query}",
        titles=title_hits,
        excerpt_per_book=data_in_page,
        pagination=pagination,
        query=query,
        tag=tag,
        sort_by=sort_by,
    )


# Show the file
@app.route("/show/<int:number>", defaults={"start_from": 0})
@app.route("/show/<int:number>/<int:start_from>")
def show(number, start_from):
    cursor = get_db().cursor()
    cursor.execute("select * from books where number = ?", (str(number),))
    data = sqlresult_to_an_entry(cursor.fetchone())

    if request.referrer == None or "edit" in request.referrer:
        prev_url = url_for("index")
    else:
        prev_url = request.referrer

    if data['pagenum'] == None:
        flash(f"Page number is not set. Please refresh the entry", "failed")
        return redirect(prev_url)

    return render_template(
        "viewer.html", data=data, start_from=start_from, prev_url=prev_url
    )


# Returns the original file
@app.route("/raw/<int:number>")
def raw(number):
    cursor = get_db().cursor()
    cursor.execute("select * from books where number = ?", (str(number),))
    data = sqlresult_to_an_entry(cursor.fetchone())

    return redirect(
        url_for("static", filename="documents/" + str(number) + "." + data["filetype"])
    )


# Returns the image of a page
@app.route("/img/<int:number>/<int:page>")
def page_image(number, page, shrink=True):
    cursor = get_db().cursor()
    cursor.execute("select * from books where number = ?", (str(number),))
    data = sqlresult_to_an_entry(cursor.fetchone())

    filetype = data["filetype"]
    filename = str(number) + f".{filetype}"
    file_real = os.path.join(app.config["UPLOAD_FOLDER"], filename)

    if filetype == "pdf":
        try:
            img = pdf2img(file_real, page=page, dpi=175)
        except IndexError:
            abort(404)
        return send_pil_image(img, imgtype="JPEG", shrink=shrink)

    elif filetype == "zip":
        try:
            img, imgtype, imgmode = zipcat(
                file_real, page=page
            )  # *** REFACT or RECONSIDER ***
        except IndexError:
            abort(404)
        return send_pil_image(img, imgtype=imgtype, imgmode=imgmode, shrink=shrink)

    else:
        flash("Image not supported yet", "failure")
        return redirect(url_for("index"))


# Uploading
# *** REFACT *** ...which variable space should be used?
app.config["UPLOAD_FOLDER"] = UPLOADDIR_PATH
app.config["THUMBNAIL_FOLDER"] = THUMBDIR_PATH
# app.config["MAX_CONTENT_LENGTH"] = 300 * 1000 * 1000 # Filesize limit if you like


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT_MIMETYPE.values()


@app.route("/upload", methods=["GET", "POST"])
def upload_file():
    files = []
    if request.method == "POST":
        # Download URL and register
        if "file_url" in request.form.keys() and request.form['file_url'] != '':
            try:
                response = requests.get(request.form['file_url'])
            except:
                flash("Specified URL is not found", "failed")
                response = False

            if response:
                mimetype = response.headers['Content-Type'].split(';')[0]
                if mimetype not in ALLOWED_EXT_MIMETYPE.keys():
                    flash(f"File from {request.form['file_url']} is not suitable type", "failed")
                    return redirect(request.url)
                
                filename = os.path.basename(response.url)
                if filename == '':
                    filename = 'downloaded'

                # Contain into werkzeug's filestorage
                a_file = FileStorage(io.BytesIO(response.content), 
                                content_type=mimetype, 
                                content_length=len(response.content),
                                filename=filename)            
                files.append(a_file)

        # Files uploaded
        files.extend(request.files.getlist("file"))

        # Filename check
        for a_file in files:
            if a_file.filename == "":
                continue
            if not allowed_file(a_file.filename):
                flash(f"Not suitable file type for {a_file.filename}", "failed")
                continue

            if a_file:
                try:
                    new_number = register_file(a_file, DB=get_db())
                    if new_number > 0:
                        flash(f'{a_file.filename} was successfully registered as #{new_number}','success')
                except (TypeError, OSError, KeyError) as e:
                    flash(str(e), 'failed')
                    continue
                except sqlite3.Error as e:
                    # This case the situation is bad.
                    flash(e, 'failed')
                    break

                # Refresh the entry metadata
                refresh_entry(new_number, DB=get_db())

        # After the for loop
        return redirect(url_for("index"))

    elif request.method == "GET":
        return render_template("upload.html", title="Upload", allowed_types=', '.join(ALLOWED_EXT_MIMETYPE.values()))


# Edit the detail
def dict2sql(data: dict, datatype: dict):  # Casting from python to sql table
    for db_k in datatype.keys():
        # *** REFACT *** not to hard-code and clarify the purpose...
        if db_k in ["hide", "spread", "r2l"]:
            data[db_k] = 1 if (db_k in data.keys() and data[db_k] == "on") else 0
        if datatype[db_k] == "INTEGER":
            data[db_k] = int(data[db_k]) if data[db_k] not in [None, "None", ""] else 0
        if datatype[db_k] == "TEXT":
            data[db_k] = str(data[db_k]).strip()[:1000] # Limitation
    return data


@app.route("/edit/<int:number>", methods=["GET", "POST"])
def edit_fileinfo(number):
    cursor = get_db().cursor()

    if request.method == "POST":
        cursor.execute("select name, type from pragma_table_info('books')")
        col_type = dict([d[0:2] for d in cursor.fetchall()])

        form_data = dict(request.form.items())
        data = dict2sql(form_data, col_type)

        named_sql = ','.join([f'{k}=:{k}' for k in col_type.keys() if k != 'number'])
        sql_values = {k: data[k] for k in col_type.keys()}
        cursor.execute(f"update books set {named_sql} where number=:number", sql_values)
        cursor.connection.commit()
        flash("Data has been modified", "success")

        # Moving into the previous page, or index if there's no history.
        if "prev_edit" in session.keys() and session["prev_edit"] != None:
            return redirect(session["prev_edit"])
        else:
            return redirect(url_for("index"))

    elif request.method == "GET":
        session["prev_edit"] = request.referrer  # Save where are you from
        cursor.execute("select * from books where number = ?", (str(number),))
        data = sqlresult_to_an_entry(cursor.fetchone())
        col_names = [d[0] for d in cursor.description]
        return render_template("edit.html", data=data, hide_keys=HIDE_KEYS)


# Remove entry
# for foolproof this cannot be called by GET.
@app.route("/remove", methods=["POST"])
def remove_entry():
    if request.method == "POST":
        form_data = dict(request.form.items())
        number = form_data["number"]
        cursor = get_db().cursor()

        # Choose the entry
        cursor.execute("select filetype from books where number = ?", (number,))
        data = sqlresult_to_an_entry(cursor.fetchone())
        filetype = data["filetype"]

        # Deleting
        try:
            cursor.execute(f"delete from books where number = ?", (number,))
            cursor.execute(f"delete from fts where number like ?", (number,))
        except Exception as e:
            flash(f"SQL Error {e}", "failed")
            return redirect(url_for("index"))

        try:
            os.remove(
                os.path.join(app.config["UPLOAD_FOLDER"], str(number) + "." + filetype)
            )
            os.remove(os.path.join(app.config["THUMBNAIL_FOLDER"], str(number) + ".jpg"))
        except FileNotFoundError:
            # This should be harmless.
            pass

        cursor.connection.commit()
        flash(f"File #{number} was successfully removed", "success")
        return redirect(url_for("index"))


# Generate thumbnail and text index
@app.route("/refresh/<int:number>")
def refresh_caller(number):
    try:
        refresh_entry(number, get_db())
        flash(f"Index successfully updated for #{number}", "success")
        return redirect(url_for("index"))
    except Exception as e:
        flash(f"Error {e}", "failed")
        return redirect(url_for("index"))


# Favicon
@app.route("/favicon.ico")
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, "static"),
        "favicon.ico",
    )


# Run
if __name__ == "__main__":
    if not os.path.exists(DATABASE_PATH):
        print("Note: seems first boot. creating empty DB and folders.")
        init_db()
        os.makedirs(
            os.path.dirname(os.path.abspath(__file__)) + "/static/", exist_ok=True
        )
        os.makedirs(UPLOADDIR_PATH, exist_ok=True)
        os.makedirs(THUMBDIR_PATH, exist_ok=True)

    app.run(debug=True)
