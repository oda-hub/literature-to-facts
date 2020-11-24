FROM python:3.6

ADD requirements.txt /requirements.txt
RUN pip install --upgrade pip
RUN pip install -r /requirements.txt

ADD facts /facts
RUN pip install facts

