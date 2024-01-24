FROM python:3.12-bookworm
ENV PORT 8888

USER root

RUN apt-get update && apt-get install -y cmake libpoppler-cpp-dev fonts-noto-cjk && pip install --upgrade pip setuptools

WORKDIR /opt/fmfm
COPY requirements.txt .
RUN python -m pip install -r requirements.txt

EXPOSE $PORT
CMD gunicorn server:app -b 0.0.0.0:$PORT -c gunicorn_fmfm.py
