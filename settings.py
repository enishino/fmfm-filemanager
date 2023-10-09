import os

# Settings STUB!
SECRET_KEY = "fmfm"

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

# Search settings
EPUB_CHUNK_SPLIT = 100

# Directories
script_dir = os.path.dirname(os.path.abspath(__file__))
UPLOADDIR_PATH = script_dir + "/static/documents"
THUMBDIR_PATH = script_dir + "/static/thumbnails"
DATABASE_PATH = script_dir + "/data/data.db"
SCHEMA_PATH = script_dir + "/data/schema.sql"

# Filetype settings
ALLOWED_EXT_MIMETYPE = {
    "application/pdf": "pdf",
    "application/zip": "zip",
    "application/epub+zip": "epub",
    "text/markdown": "md",
}

# Images in zip file
IMG_MIMETYPES = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "bmp": "image/bmp",
    "tiff": "image/tiff",
    "tif": "image/tiff",
    "gif": "image/gif",
    "webp": "image/webp",
}
IMG_SUFFIX = tuple(f".{k}" for k in IMG_MIMETYPES.keys())

# True to shrink image into JPEG when transferred
IMG_SHRINK = True

# Maximum size of shrunk image (if larger than this value)
IMG_SHRINK_WIDTH, IMG_SHRINK_HEIGHT = 3840, 2160
