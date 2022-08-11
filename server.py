#!python3

import os
import io
import re
import unicodedata
import socket
import requests

from flask import Flask, render_template, request, redirect, url_for, make_response
from flask import abort, flash, session, send_file, send_from_directory
from flask import g
from flask_paginate import Pagination, get_page_parameter
from werkzeug.exceptions import NotFound
from werkzeug.datastructures import FileStorage

import sqlite3

from tools import init_db
from tools import zipcat, pdf2img, register_file, refresh_entry
from tools import n_gram, n_gram_to_txt, show_hit_text
from settings import (
    SECRET_KEY,
    DATABASE_PATH,
    SCHEMA_PATH,
    PER_PAGE_ENTRY,
    PER_PAGE_SEARCH,
    UPLOADDIR_PATH,
    THUMBDIR_PATH,
    ALLOWED_EXT_MIMETYPE,
    HIDE_KEYS,
)

# DB initialization
init_db()

# Flask initialization
app = Flask(__name__)
app.secret_key = SECRET_KEY
config = {"SESSION_COOKIE_HTTPONLY": True, "SESSION_COOKIE_SAMESITE": "Lax"}
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


def flash_and_go(message, status, toward):
    flash(message, status)
    return redirect(toward)


# Data tools
# PIL Image -> Image file
def send_pil_image(
    pil_img, imgtype="JPEG", imgmode="RGB", quality=100, shrink=False, caching=True
):
    if shrink:  # REFACT consider splitting
        imgtype = "JPEG"
        quality = 90
        imgmode = "RGB"

    pil_img = pil_img.convert(imgmode)
    img_io = io.BytesIO()
    pil_img.save(img_io, imgtype, quality=quality)
    img_io.seek(0)

    mimetypes = {"PNG": "image/png", "JPEG": "image/jpeg", "BMP": "image/bmp"}
    response = make_response(send_file(img_io, mimetype=mimetypes[imgtype]))
    if caching:
        response.headers["Cache-Control"] = "max-age=3000"
    return response


# Sorting method table
sort_methods = {
    "title_asc": ("title", "asc"),
    "title_desc": ("title", "desc"),
    "number_asc": ("number", "asc"),
    "number_desc": ("number", "desc"),
}


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
        flash("Failure on selecting sorting method", "failure")
        sort_col, sort_meth = "number", "desc"  # as default.

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


def query_cleaner(query):
    query = query.replace("\u3000", " ")  # full-width space
    query = re.sub(r" ([\&\+\(\)\*\\\#]) ", r"\1", query)  # Care for orphan symbols

    # (i) For western languages
    query_quoted = " ".join([f'"{q}"' for q in query.split(" ")])

    # (ii) for languages without delimiter
    ngram_ary = [f'"{n_gram(q)}"' if len(q) > 1 else q for q in query.split(" ")]
    query_ngram = "(" + " ".join(ngram_ary) + ")"

    # (iii) (i) and (ii) are merged
    query_merged = query_quoted + " OR " + query_ngram
    return query_merged


@app.route("/search")
def search():
    cursor = get_db().cursor()
    query = request.args.get("query", type=str, default="")
    tag = request.args.get("tag", type=str, default="")
    sort_by = request.args.get("sort_by", type=str, default="title_asc")
    sort_col, sort_meth = "title", "asc"  # Default method

    # No query no result
    if query == "":
        return redirect(url_for("index", tag=tag))

    # Meanless query no result
    query_merged = query_cleaner(query)
    if query_merged.strip() == "":
        return flash_and_go(
            f"No meaningful query generated for {query}",
            "failed",
            url_for("index", tag=tag),
        )

    # Call SQL to run full-text search
    cursor.execute(
        """
        select * from fts where ngram match :textquery
        order by bm25(fts) limit 500 
        """,
        {
            "textquery": query_merged,
        },
    )

    # Format results into book->page->Ngram
    fts_result = cursor.fetchall()
    fts_excerpt = {x: {} for x in [r["number"] for r in fts_result]}
    for d in fts_result:
        d = dict(d)
        orig_txt = n_gram_to_txt(d["ngram"])
        excerpted = show_hit_text(orig_txt, query)
        if excerpted == "...":
            continue
        fts_excerpt[d["number"]].update({d["page"]: excerpted})

    # Re-search DB for title and get Book title from FTS search
    numbers = ",".join([str(s) for s in fts_excerpt.keys()])
    # * I'm not sure this SQL good or bad...
    cursor.execute(
        f"""
        select * from Books where title like :title
        or number in ({numbers})
        """,
        {
            "title": "%" + query + "%",
        },
    )
    ngram_with_title = cursor.fetchall()

    # Update full-text result with title result
    for i in ngram_with_title:
        entry = dict(i)
        num, title = entry["number"], entry["title"]
        # Insert title into result dict
        if num in fts_excerpt.keys():
            fts_excerpt[num].update({"title": title})
        else:
            fts_excerpt[num] = {"title": title}
        # If title only matches
        if query.lower() in title.lower():
            fts_excerpt[num].update({0: "[Document Title matches]"})

    # Page position control
    page = request.args.get(get_page_parameter(), type=int, default=1)
    per_page = request.args.get("per_page", type=int, default=PER_PAGE_SEARCH)

    # Paginate data
    start_at = per_page * (page - 1)
    end_at = per_page * (page)
    data_in_page = dict(list(fts_excerpt.items())[start_at:end_at])

    # Split result into pages
    pagination = Pagination(
        page=page,
        total=len(fts_excerpt),
        per_page=per_page,
        css_framework="bootstrap5",
    )

    return render_template(
        "search.html",
        title=f"Search result for {query}",
        excerpt_per_book=data_in_page,
        pagination=pagination,
        query=query,
        tag=tag,
        sort_by=sort_by,
    )


# Show the file
@app.route("/show/<int:number>", defaults={"start_from": 0})
@app.route("/show/<int:number>/<int:start_from>")
@app.route("/show/<int:number>/<float:start_from>")
def show(number, start_from):
    cursor = get_db().cursor()
    cursor.execute("select * from books where number = ?", (str(number),))
    data = sqlresult_to_an_entry(cursor.fetchone())

    if data["filetype"] == "epub":
        return render_template(
            "epub_bibi.html",
            title=data["title"],
            book=str(number) + "." + data["filetype"],
            iipp=float(start_from) + 0.001,  # Workaround for correct positioning
        )

    else:
        if request.referrer is None or "edit" in request.referrer:
            prev_url = url_for("index")
        else:
            prev_url = request.referrer

        if data["pagenum"] is None:
            return flash_and_go(
                "Page number is not set. Please refresh the entry", "failed", prev_url
            )

        return render_template(
            "viewer.html", data=data, start_from=start_from, prev_url=prev_url
        )


# Returns the original file
# * Reconsider if SQL is really required
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

    try:
        if filetype == "pdf":
            img = pdf2img(file_real, page=page, dpi=175)
            imgtype = "JPEG"
            imgmode = "RGB"
        elif filetype == "zip":
            img, imgtype, imgmode = zipcat(file_real, page=page)
        else:
            return flash_and_go("Image not supported yet", "failure", url_for("index"))
        return send_pil_image(img, imgtype=imgtype, imgmode=imgmode, shrink=shrink)
    except IndexError:
        abort(404)


# Uploading
# *** REFACT *** ...which variable space should be used?
app.config["UPLOAD_FOLDER"] = UPLOADDIR_PATH
app.config["THUMBNAIL_FOLDER"] = THUMBDIR_PATH


def is_allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT_MIMETYPE.values()
    )


def get_remote_file(url):
    if url == "" or url == None:
        return None

    try:
        response = requests.get(url)
    except requests.exceptions.RequestException:
        flash("Specified URL is not found", "failed")
        return None

    mimetype = response.headers["Content-Type"].split(";")[0]
    if mimetype not in ALLOWED_EXT_MIMETYPE.keys():
        return flash_and_go(
            "{request.form['file_url']} is not suitable type", "failed", request.url
        )

    # Contain into werkzeug's filestorage
    a_file = FileStorage(
        io.BytesIO(response.content),
        content_type=mimetype,
        content_length=len(response.content),
        filename=os.path.basename(response.url) or "downloaded",
    )
    return a_file


@app.route("/upload", methods=["GET", "POST"])
def upload_file():
    files = []

    if request.method == "POST":
        # Files (uploaded)
        files.extend(request.files.getlist("file"))

        # Download URL and register
        a_file = get_remote_file(request.form["file_url"])
        if a_file:
            files.append(a_file)

        # Filetype, filename check
        for a_file in files:
            if not isinstance(a_file, FileStorage):
                continue
            if not a_file.filename:
                continue
            if not is_allowed_file(a_file.filename):
                flash(f"Not suitable file type for {a_file.filename}", "failed")
                continue

            try:
                new_number = register_file(a_file, database=get_db())
                refresh_entry(new_number, database=get_db())
                flash(
                    f"{a_file.filename} was registered as #{new_number}",
                    "success",
                )

            except (TypeError, OSError, KeyError) as e:
                flash(str(e), "failed")
                continue
            except sqlite3.Error as e:
                flash(str(e), "failed")
                break

        # After registering loop
        return redirect(url_for("index"))

    elif request.method == "GET":
        return render_template(
            "upload.html",
            title="Upload",
            allowed_types=", ".join(ALLOWED_EXT_MIMETYPE.values()),
        )


# Edit the detail
def dict2sql(data: dict, datatype: dict):  # Casting from python to sql table
    for db_k in datatype.keys():
        # *** REFACT *** not to hard-code and clarify the purpose...
        if db_k in ["hide", "spread", "r2l"]:
            data[db_k] = 1 if (db_k in data.keys() and data[db_k] == "on") else 0

        if datatype[db_k] == "INTEGER":
            data[db_k] = int(data[db_k]) if data[db_k] not in [None, "None", ""] else 0

        if datatype[db_k] == "TEXT":
            data[db_k] = str(data[db_k]).strip()[:1000]  # Cut off too long string
    return data


@app.route("/edit/<int:number>", methods=["GET", "POST"])
def edit_fileinfo(number):
    cursor = get_db().cursor()

    if request.method == "POST":
        cursor.execute("select name, type from pragma_table_info('books')")
        col_type = dict([d[0:2] for d in cursor.fetchall()])

        form_data = dict(request.form.items())
        data = dict2sql(form_data, col_type)

        named_sql = ",".join([f"{k}=:{k}" for k in col_type.keys() if k != "number"])
        sql_values = {k: data[k] for k in col_type.keys()}
        cursor.execute(f"update books set {named_sql} where number=:number", sql_values)
        cursor.connection.commit()
        flash("Data has been modified", "success")

        # Moving into the previous page, or index if there's no history.
        if "prev_edit" in session.keys() and session["prev_edit"] is not None:
            return redirect(session["prev_edit"])
        else:
            return redirect(url_for("index"))

    elif request.method == "GET":
        session["prev_edit"] = request.referrer  # Save where you are from
        cursor.execute("select * from books where number = ?", (str(number),))
        data = sqlresult_to_an_entry(cursor.fetchone())
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
        # * slow! what is the reason?
        try:
            cursor.execute("delete from books where number = ?", (number,))
            cursor.execute("delete from fts where number like ?", (number,))
        except Exception as e:
            return flash_and_go(f"SQL Error {e}", "failed", url_for("index"))

        try:
            # Remove the book file
            os.remove(
                os.path.join(app.config["UPLOAD_FOLDER"], str(number) + "." + filetype)
            )
            # Remove thumbnail image
            os.remove(
                os.path.join(app.config["THUMBNAIL_FOLDER"], str(number) + ".jpg")
            )
        except FileNotFoundError:
            pass

        cursor.connection.commit()
        return flash_and_go(
            f"File #{number} was successfully removed", "success", url_for("index")
        )


# Generate thumbnail and text index
@app.route("/refresh/<int:number>")
def refresh_caller(number):
    try:
        refresh_entry(number, get_db())
        return flash_and_go(
            f"Index successfully updated for #{number}", "success", url_for("index")
        )
    except Exception as e:
        return flash_and_go(f"Error {e}", "failed", url_for("index"))


# Favicon
@app.route("/favicon.ico")
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, "static"),
        "favicon.ico",
    )


# Run
if __name__ == "__main__":
    app.run(debug=True)
