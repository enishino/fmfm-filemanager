import os

# Settings STUB!
# Interface
PER_PAGE_ENTRY = 50
PER_PAGE_SEARCH = 5
HIDE_KEYS = [
    "number",
    "filetype",
    "md5",
    "pagenum",
    "state_num",
    "document_date",
    "registered_date",
    "modified_date",
]

# Directories
script_dir = os.path.dirname(os.path.abspath(__file__))
UPLOADDIR_PATH = script_dir + "/static/documents"
THUMBDIR_PATH = script_dir + "/static/thumbnails"
DATABASE_PATH = script_dir + "/data/data.db"
SCHEMA_PATH = script_dir + "/data/schema.sql"

# Filetype settings
ALLOWED_EXT_MIMETYPE = {"application/pdf": "pdf", "application/zip": "zip"}
IMG_SUFFIX = (".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".gjf")
