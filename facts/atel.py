import logging
import typing
import re
import os
import sys
import json
import requests
import click
import time
import urllib.parse
import glob
from datetime import datetime

from facts.core import workflow

logger = logging.getLogger()

ATelEntry = typing.NewType("ATelEntry", dict)

@click.group()
@click.option("--debug", "-d", default=False, is_flag=True)
def cli(debug=False):
    if debug:
        logger.setLevel(logging.DEBUG)

class BoringAtel(Exception):
    "boring"

@workflow
def atel_date(entry: ATelEntry) -> dict:  # date
    t = datetime.strptime(
        entry['date'].strip(), "%d %b %Y; %H:%M UT").timestamp()

    return dict(timestamp=t)

@cli.command('parse-html')
@click.argument("html")
def parse_html(html):
    index = open(html).read()

    index = re.sub('<tr', r'\n<tr', index)
    open("degoogled.html", "w").write(index)


    logger.debug("got file of %s bytes", len(index))

    es=[]
    for l in re.findall('<tr valign="top"><td class="num">(\d+)</td>'+
                        '<td class="title"><a href="(http.*?)">(.*?)</a></td>'+
                        '<td class="author" valign="top">(.*?)<BR><EM>(.*?)</EM></TD></TR>',
                        index,
                        re.I | re.M | re.S 
                        ):
        entry = dict(zip(['atelid', 'url', 'title', 'authors', 'date'], 
                [ i.replace("\n", " ") for i in l ]))
        logging.debug("%s", entry)
        es.append(entry)

    logger.info("found in total %s entries", len(es))

    json.dump(es, open('atels.json','w'))


@cli.command('fetch')
def fetch():
    index = requests.get('http://www.astronomerstelegram.org/').text

    es=[]
    for l in re.findall('<TR valign=top><TD  class="num"  >(\d+)</TD>'+
                        '<TD class="title"><A HREF="(http.*?)">(.*?)</A></TD>'+
                        '<TD  class="author" valign=top>(.*?)<BR><EM>(.*?)</EM></TD></TR>',
                        index):
        entry = dict(zip(['atelid', 'url', 'title', 'authors', 'date'], l))
        logging.debug("%s", entry)
        es.append(entry)

    json.dump(es, open('atels.json','w'))

@workflow
def mentions_keyword(entry: ATelEntry):  # ->
    d = {} # type: typing.Dict[str, typing.Any]

    for keyword in "INTEGRAL", "FRB", "GRB", "GW170817", "GW190425", "magnetar", "SGR":
        k = keyword.lower()

        for field in 'title',:
            n = len(re.findall(keyword, entry[field]))
            if n>0:
                d['mentions_'+k] = field
            if n>1:
                d['mentions_'+k+'_times'] = n

    return d

@workflow
def basic_meta(entry: ATelEntry):  # ->$                                                                                
    return dict(
            location=entry['url'],
            title=re.sub(r"[\n\r]", " ", entry['title']),
            source="ATel",
        )


@workflow
def list_entries() -> typing.List[ATelEntry]:
    es = json.load(open('atels.json'))

 #   index = requests.get('http://www.astronomerstelegram.org/').text

    return es

@workflow
def identity(entry: ATelEntry) -> str:
    return 'http://odahub.io/ontology/paper#atel'+entry['atelid'].split("/")[-1]

@cli.command("list")
def listthem():
    list_entries()

if __name__ == "__main__":
    cli()
