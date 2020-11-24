FROM python:3.8

ADD requirements.txt /requirements.txt
RUN pip install --upgrade pip
RUN pip install -r /requirements.txt

ADD dist /dist
RUN pip install /dist/*

ADD entrypoint.sh /entrypoint.sh

ENTRYPOINT [ "bash", "/entrypoint.sh" ]
