FROM python:3.8-bullseye
USER root

RUN apt-get update
RUN apt-get install -y cmake libpoppler-cpp-dev # for poppler-python

RUN pip install --upgrade pip
RUN pip install --upgrade setuptools

COPY . .

RUN python -m pip install -r requirements.txt
EXPOSE 8888
CMD gunicorn server:app -c gunicorn_fmfm.py
