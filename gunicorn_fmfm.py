import os

wsgi_app = "fmfm.wsgi:application"

bind = "0.0.0.0:" + str(os.getenv("PORT", 8888))
proc_name = "FMFM"
workers = 2
threads = 1
timeout = 6000
