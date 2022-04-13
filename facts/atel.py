import email.parser
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
from facts import common

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
    for l in re.findall(r'<tr valign="top"><td class="num">(\d+)</td>'+
                        r'<td class="title"><a href="(http.*?)">(.*?)</a></td>'+
                        r'<td class="author" valign="top">(.*?)<BR><EM>(.*?)</EM></TD></TR>',
                        index,
                        re.I | re.M | re.S 
                        ):
        entry = dict(zip(['atelid', 'url', 'title', 'authors', 'date'], 
                [ i.replace("\n", " ") for i in l ]))
        logging.debug("%s", entry)
        es.append(entry)

    logger.info("found in total %s entries", len(es))

    json.dump(es, open('atels.json','w'))

def atel_cache_fn(t):
    return os.path.join(os.getenv("HOME", "/tmp"), f".cache/atels/{t}.txt")

def parse_atel_email(f):
    message = email.parser.BytesParser().parse(f)
    logger.debug('found message payload %s', message.get_payload())
    atel_text = message.get_payload()

    entry = dict()

    for atel_field, field, endt in [
        ('Title', 'title', 'Author:'),
        ('Author', 'authors', 'Queries:'),
        ('Queries', 'submitter_email', 'Posted:'),
        ('Posted', 'date', 'Subjects:'),
        ('Subjects', 'tags', '\n\n')
    ]:                    
        entry[field] = re.search(f"{atel_field}:(.*?)(?={endt})", atel_text, re.S).group(1)
        entry[field] = re.sub("[\t\r\n]+", " ", entry[field]).strip()

    entry['authors'] = entry['authors'].split(";", 1)[-1].strip()
    entry['atelid'] = re.search(r"ATEL #(\d+)", atel_text).group(1).strip()

    entry['url'] = f"https://www.astronomerstelegram.org/?read={entry['atelid']}"

    entry['body'] = re.search(r"Subjects:.*?\n\n(.*?)[=\-]{20,}", atel_text, re.S).group(1)
    entry['body'] = re.sub("[\n\r\t ]+", " ", entry['body'])

    logging.debug("%s", json.dumps(entry, indent=4, sort_keys=True))

    return entry

def parse_atel_cache_id(atelid):
    with open(atel_cache_fn(atelid), "rb") as f:
        return parse_atel_email(f)

@cli.command('fetch')
#TODO: control all vs recent
def fetch():    
    es = []

    for fn in glob.glob(atel_cache_fn("*")):
        # entry = dict(zip(['atelid', 'url', 'title', 'authors', 'date'], l))
        # logging.debug("%s", entry)
        # es.append(entry)
        with open(fn, "rb") as f:            
            es.append(parse_atel_email(f))
            
        # break

    json.dump(es, open('atels.json','w'))

@cli.command('fetch-web')
#TODO: control all vs recent
def fetch_web():
    index = requests.get('http://www.astronomerstelegram.org/').text
    #index = requests.get('http://www.astronomerstelegram.org/?displayall').text
    # index = open("The Astronomer's Telegram.html").read()

    print('got index of', len(index))
        
    es=[]
    # for l in re.findall(r'<TR valign=top><TD  class="num"  >(\d+)</TD>'+
    #                     r'<TD class="title"><A HREF="(http.*?)">(.*?)</A></TD>'+
    #                     r'<TD  class="author" valign=top>(.*?)<BR><EM>(.*?)</EM></TD></TR>',
    for l in re.findall((r'<tr valign="top"><td class="num">(\d+)</td>'
                         r'<td class="title"><a href="(.*?)">(.*?)</a></td>'
                         r'<td class="author" valign="top">(.*?)<br><em>(.*?)</em></td></tr>'),
                        index,
                        re.I):
        entry = dict(zip(['atelid', 'url', 'title', 'authors', 'date'], l))
        logging.debug("%s", entry)
        es.append(entry)


    json.dump(es, open('atels.json','w'))

@workflow
def mentions_keyword(entry: ATelEntry):  # ->
    return common.mentions_keyword(entry['title'], entry['body'])


@workflow
def mentions_named(entry: ATelEntry):  # ->
    return common.mentions_grblike(entry['title'], entry['body'])


@workflow
def basic_meta(entry: ATelEntry):  # ->$                                                                                
    return dict(
            location=entry['url'],
            title=re.sub(r"[\n\r]", " ", entry['title']),
            source="ATel",
            atelid=entry['atelid'],
        )


@workflow
def list_entries() -> typing.List[ATelEntry]:
    es = json.load(open('atels.json'))

    return es


@workflow
def identity(entry: ATelEntry) -> str:
    return 'http://odahub.io/ontology/paper#atel'+entry['atelid'].split("/")[-1]

@cli.command("list")
def listthem():
    list_entries()

if __name__ == "__main__":
    cli()
