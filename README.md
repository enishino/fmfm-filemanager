# fmfm: fast minimum file manager
A web-based document manager/viewer upon Flask+Python. Currently PDF, zip file (including images) and epub documents are supported.

**This is still in beta stage and the code is not secure. Please do not use this on public servers.**

## List view
Clicking thumbnail opens the viewer. The right bottom "PDF" badge jumps into the original file. Document tagging and searching are supported.

<img src="images/1_listview.png" alt="List of files" width="600px" />

## Viewer
Tiny HTML-based document viewer (for PDF and zip) is included. Capabilities:
* Single page / Spread view
* Left-to-right / Right-to-left
* One page shifting (to correct facing page layout)

<img src="images/2_viewer.png" alt="Viewer" width="500px" />

Epub reading is powered by [Bibi][https://github.com/satorumurmur/bibi]. (This is a fantastic software!)

## Search
Full-text search (PDF and epub)

<img src="images/3_search.png" alt="Search" width="500px" />

日本語も検索可能です Japanese search is supported. (tokenizer: 2-gram)

<img src="images/4_Japanese_search.png" alt="Japanese-search" width="500px" />

## Edit metadata
* Edit menu is called from green button at bottom left on thumbnail.
* Multiple tags by separating them with a whitespace.
* `r2l`: the document is right-to-left (PDF and zip)
* `spread`: the document is shown in spread view (PDF and zip)
* `hide`: hides the document; it works, but **currently the file found by search**.

<img src="images/5_edit.png" alt="edit page" width="300px" />

## Other features
* Multi-file uploading
* Ignores already registered file when uploading (by MD5 hash)
* Batch importing, by putting files into `inbox` folder and call `python importer.py`

## Install and run
1. `git clone` this repository and `cd` into the folder
1. Modify `SECRET_KEY` to something random string in `settings.py`
1. Download `Bibi-v1.2.0.zip` from [here][https://github.com/satorumurmur/bibi/releases/tag/v1.2.0], unpack the file and move `Bibi-v1.2.0` folder into `static` folder.

* Docker
1. Do `docker-compose up -d`
1. Access to `http://localhost:8888` by a web browser.
1. You can stop the container by `docker container stop fmfm-filemanager-python3-1`.

* Linux (local)
1. `pip install -r requirements.txt` (You also need `cmake` and `poppler-cpp` package in a distro)
1. `python server.py` or `bash run_fmfm_local.sh`
1. Access to `http://localhost:5000/` (Former) or `http://localhost:8888/` (Latter) by a web browser.

## Tips
* Caching images by nginx improves the performance. See `nginx_conf.sample` for example.

## Limitations and bugs
### Overall
* The code is ugly, repeating phrases and not well-formatted ;(
### Viewer
* PDF Viewer shows just an image, so in-page search is not possible.
* PDF rendering is a bit heavy task, for SBCs like raspberry pi (RPi4 handles tasks well in my house though;)
* To suppress transfer size the result is compressed with JPEG, so the viewer shows lossy image.
* All the image is set to be cached. Please clear browser cache if you found odd behavior.
### Search
* Full-text search with tag search is not possible yet.
* Search by date will be (IMHO) implemented but not yet.
### Upload
* Making index is a heavy task and sometimes a gateway timeout happens.
