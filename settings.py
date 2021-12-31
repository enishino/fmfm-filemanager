import os

# Settings STUB!
# Interface
PER_PAGE_ENTRY = 50
PER_PAGE_SEARCH = 5
HIDE_KEYS = ['number', 'filetype', 'md5', 'pagenum', 'state_num', 'document_date', 'registered_date', 'modified_date']

# Directories
UPLOADDIR_PATH = os.path.dirname(os.path.abspath(__file__)) + '/static/documents'
THUMBDIR_PATH = os.path.dirname(os.path.abspath(__file__)) + '/static/thumbnails'
DATABASE_PATH = os.path.dirname(os.path.abspath(__file__)) + '/data/data.db'
SCHEMA_PATH = os.path.dirname(os.path.abspath(__file__)) + '/data/schema.sql'

# Filetype settings
ALLOWED_EXTENSIONS = {"pdf", "zip"}
IMG_SUFFIX = (".jpg", ".png", ".bmp", ".tiff", "*.gjf")
