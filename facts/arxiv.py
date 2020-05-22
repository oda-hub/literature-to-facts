import logging
import typing
import re
import sys
import json
import requests
import feedparser
import click
import time
import urllib.parse
from datetime import datetime

from facts.core import workflow

logger = logging.getLogger()

PaperEntry = typing.NewType("PaperEntry", dict)

@click.group()
@click.option("--debug", "-d", default=False, is_flag=True)
def cli(debug):
    if debug:
        logger.setLevel(logging.DEBUG)


class BoringPaper(Exception):
    "boring"


@cli.command()
@click.option("-s", "--search-string")
@click.option("-c", "--category", default="astro-ph")
@click.option("-n", "--max-results", default=10)
def fetch(search_string, max_results, category):
    params = dict(
        search_query=f'{search_string}',
        sortBy='lastUpdatedDate',
        sortOrder='descending',
        max_results=max_results
    )

    r = requests.get('http://export.arxiv.org/api/query?'+ urllib.parse.urlencode(params, doseq=True))

    feed = feedparser.parse(r.text)
    json.dump(feed, open("recent.json", "w"))

    for entry in feed['entries']:
        logger.debug(f'fetched {entry["id"].split("/")[-1]} ({entry["updated"]}): {entry["title"]}')

@cli.command()
def fetch_recent():
    r = requests.get('http://arxiv.org/rss/astro-ph')
    json.dump(feedparser.parse(r.text), open("recent.json", "w"))

@workflow
def basic_meta(entry: PaperEntry):  # ->
    updated_ts = datetime.fromisoformat(entry['updated'].replace('Z',"")).timestamp()
    return dict(
                location=entry['id'], 
                title=re.sub(r"[\n\r]", " ", entry['title']),
                updated_isot=entry['updated'],
                updated_ts=updated_ts,
            )


@workflow
def mentions_keyword(entry: PaperEntry):  # ->
    d = {}

    for keyword in "INTEGRAL", "FRB", "GRB", "GW170817", "GW190425", "magnetar", "SGR":
        k = keyword.lower()

        for field in 'title', 'summary':
            n = len(re.findall(keyword, entry[field]))
            if n>0:
                d['mentions_'+k] = field
            if n>1:
                d['mentions_'+k+'_times'] = n
        

    return d

@workflow
def list_entries() -> typing.List[PaperEntry]:
    return json.load(open("recent.json"))['entries']

@workflow
def identity(entry: PaperEntry) -> str:
    return 'http://odahub.io/ontology/paper#'+entry['id'].split("/")[-1]

if __name__ == "__main__":
    cli()
