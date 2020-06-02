import logging
import typing
from concurrent import futures
import re
import os
import sys
import json
from datetime import datetime
import requests
import click
import rdflib # type: ignore
from colorama import Fore, Style # type: ignore

from facts.core import workflow

logger = logging.getLogger()

GCNText = typing.NewType("GCNText", str)


@click.group()
@click.option("--debug", "-d", default=False, is_flag=True)
def cli(debug):
    if debug:
        logger.setLevel(logging.DEBUG)


class NoSuchGCN(Exception):
    "no such"


class BoringGCN(Exception):
    "boring"


def gcn_source(gcnid: int, allow_net=False) -> GCNText:  # -> gcn
    try:
        t = open(f"gcn3/{gcnid}.gcn3", "rb").read().decode('ascii', 'replace')
        return GCNText(t)
    except FileNotFoundError:
        if allow_net:
            t = requests.get("https://gcn.gsfc.nasa.gov/gcn3/%i.gcn3" % gcnid).text
            return GCNText(t)

    raise NoSuchGCN(gcnid)


@cli.command("fetch-tar")
def fetch_tar():
    logger.debug("https://gcn.gsfc.nasa.gov/gcn3/all_gcn_circulars.tar.gz")
    os.system("curl https://gcn.gsfc.nasa.gov/gcn3/all_gcn_circulars.tar.gz | tar xvzf -")

@workflow
def identity(gcntext: GCNText):
    gcnid = int(re.search(f"NUMBER:(.*)", gcntext).groups()[0])
    return f"http://odahub.io/ontology/paper#gcn{gcnid:d}"

@workflow
def gcn_list_recent() -> typing.List[GCNText]:
    gt = requests.get("https://gcn.gsfc.nasa.gov/gcn3_archive.html").text

    r = re.findall(r"<A HREF=(gcn3/\d{1,5}.gcn3)>(\d{1,5})</A>", gt)

    logger.debug(f"results {len(r)}")

    for u, i in reversed(r):
        logger.debug(f"{u} {i}")

        try:
            yield gcn_source(i)
        except NoSuchGCN:
            logger.warning(f"no GCN: {i}")


@workflow
def gcn_instrument(gcntext: GCNText):
    instruments = []

    for i, m in [
            ("fermi-gbm", "Fermi/GBM"),
            ("fermi-gbm", "Fermi GBM"),
            ("fermi-lat", "Fermi/LAT"),
            ("agile", "AGILE"),
    ]:
        if re.search(f"SUBJECT:.*{m}.*", gcntext):
            instruments.append(i)

    return dict(instrument=instruments)


@workflow
def mentions_keyword(gcntext: GCNText):  # ->$                                                                                                                                                                
    d = {}

    for keyword in "INTEGRAL", "FRB", "GRB", "GW170817", "GW190425", "magnetar", "SGR", "SPI-ACS":
        k = keyword.lower()

        n = len(re.findall(keyword, gcntext))
        if n>0:
            d['mentions_'+k] = "body"
        if n>1:
            d['mentions_'+k+'_times'] = n

    return d

@workflow
def gcn_meta(gcntext: GCNText):  # ->
    d = {}

    for c in "DATE", "SUBJECT", "NUMBER":
        d[c] = re.search(c+":(.*)", gcntext).groups()[0].strip()

    d['location'] = f"https://gcn.gsfc.nasa.gov/gcn3/{d['NUMBER']}.gcn3"
    d['title'] = d['SUBJECT']
    d['source'] = "GCN"

    return d


@workflow
def gcn_date(gcntext: GCNText) -> dict:  # date
    t = datetime.strptime(
        gcn_meta(gcntext)['DATE'], "%y/%m/%d %H:%M:%S GMT").timestamp()

    return dict(timestamp=t)

@workflow
def gcn_named(gcntext: GCNText):  # ->
    r = re.search("SUBJECT: *(GRB.*?):.*", gcntext, re.I)

    grb_name = r.groups()[0].strip().replace(" ","")

    return dict(mentions_named_grb=grb_name)


@workflow
def gcn_integral_lvc_countepart_search(gcntext: GCNText):  # ->
    r = re.search("SUBJECT:(LIGO/Virgo.*?):.*INTEGRAL", gcntext, re.I)

    original_event = r.groups()[0].strip()

    return dict(original_event=original_event)


@workflow
def gcn_integral_countepart_search(gcntext: GCNText):  # ->
    r = re.search("SUBJECT:(.*?):.*counterpart.*INTEGRAL", gcntext, re.I)

    original_event = r.groups()[0].strip()

    original_event_utc = re.search(
        r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) UTC, hereafter T0", gcntext).groups()[0]

    instruments = []
    if re.search("SUBJECT:(.*?):.*ACS.*", gcntext, re.I):
        instruments.append("acs")

    if re.search("SUBJECT:(.*?):.*IBIS.*", gcntext, re.I):
        instruments.append("ibis")

    return dict(
        original_event=original_event,
        original_event_utc=original_event_utc,
        instrument=instruments,
    )


@workflow
def gcn_icecube_circular(gcntext: GCNText):  # ->
    r = re.search("SUBJECT:(.*?)- IceCube observation of a high-energy neutrino candidate event",
                  gcntext, re.I).groups()[0].strip()

    return dict(reports_icecube_event=r)


@workflow
def gcn_lvc_circular(gcntext: GCNText):  # ->
    r = re.search("SUBJECT:.*?(LIGO/Virgo .*?): Identification",
                  gcntext, re.I).groups()[0].strip()

    return dict(lvc_event_report=r)


@workflow
def gcn_grb_integral_circular(gcntext: GCNText):  # ->
    r = re.search("SUBJECT:.*?(GRB.*?):.*INTEGRAL.*",
                  gcntext, re.I).groups()[0].strip()

    grbname = r

    grbtime = re.search(r"(\d\d:\d\d:\d\d) +UT",
                        gcntext, re.I).groups()[0].strip()

    date = grbname.replace("GRB", "").strip()
    utc = "20" + date[:2] + "-" + date[2:4] + "-" + date[4:6] + " " + grbtime

    return dict(integral_grb_report=grbname, event_t0=utc)


@workflow
def gcn_lvc_integral_counterpart(gcntext: GCNText):  # ->
    re.search("SUBJECT:.*?(LIGO/Virgo .*?):.*INTEGRAL",
              gcntext, re.I).groups()[0].strip()

    return dict(lvc_counterpart_by="INTEGRAL")

if __name__ == "__main__":
    cli()
