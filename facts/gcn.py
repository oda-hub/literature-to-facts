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
def cli(debug=False):
    if debug:
        logger.setLevel(logging.DEBUG)


class NoSuchGCN(Exception):
    "no such"


class BoringGCN(Exception):
    "boring"


@workflow
def gcn_source(gcnid: int, allow_net=True) -> GCNText:
    try:
        t = open(f"gcn3/{gcnid}.gcn3", "rb").read().decode('ascii', 'replace')
        return GCNText(t)
    except FileNotFoundError:
        if allow_net:
            r = requests.get("https://gcn.gsfc.nasa.gov/gcn3/%i.gcn3" % int(gcnid))

            if r.status_code == 200:
                t = r.text
                return GCNText(t)

    raise NoSuchGCN(gcnid)


@cli.command("fetch-tar")
def fetch_tar():
    logger.debug("https://gcn.gsfc.nasa.gov/gcn3/all_gcn_circulars.tar.gz")
    os.system("curl https://gcn.gsfc.nasa.gov/gcn3/all_gcn_circulars.tar.gz | tar xvzf -")

@workflow
def identity(gcntext: GCNText):
    r = re.search(f"NUMBER:(.*)", gcntext)

    if r is None:
        logger.error("can not find number in the GCN: {gcnid}: {e}; full text below")
        print(gcntext)
        raise Exception(f"no identity in GCN: {gcntext}")
    else:
        gcnid = int(r.groups()[0])

    return f"http://odahub.io/ontology/paper#gcn{gcnid:d}"

@workflow
def gcn_list_recent() -> typing.Generator[GCNText, None, None]:
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
    d = {} # type: typing.Dict[str, typing.Union[str, int]]

    for keyword in "HAWC", "INTEGRAL", "FRB", "GRB", "GW170817", "GW190425", "magnetar", "SGR", "SPI-ACS", "IceCube", "LIGO/Virgo", "ANTARES", "Fermi/LAT":
        k = keyword.lower()

        n = len(re.findall(keyword, gcntext))
        if n>0:
            d['mentions_'+k] = "body"
        if n>1:
            d['mentions_'+k+'_times'] = n

    return d

@workflow
def fermi_realtime(gcntext: GCNText):  # ->$                                                                                                                                                                
    d = {} # type: typing.Dict[str, typing.Union[str, int]]

    r = re.search(r"At (.*?), the Fermi Gamma-ray Burst Monitor \(GBM\) triggered", gcntext)
    #r = re.search(r"At (\d{2}:\d{2}:\d{2} UT on .*?), the Fermi Gamma-ray Burst Monitor (GBM) triggered", gcntext)
    
    if r is not None:
        d['grb_isot'] = datetime.strptime(
                r.groups()[0].strip(), 
                "%H:%M:%S UT on %d %b %Y"
            ).strftime("%Y-%m-%dT%H:%M:%S")

    return d

@workflow
def swift_detected(gcntext: GCNText):  # ->$                                                                                                                                                                
    d = {} # type: typing.Dict[str, typing.Union[str, int]]

    T = re.sub("\n", " ", gcntext, re.M | re.S)
    r = re.search(r"At (.*?) UT, the Swift Burst Alert Telescope \(BAT\) triggered and located (GRB ?.*?) ", 
                  T)
    
    if r is not None:
        print(r.groups())
        d['grb_isot'] = datetime.strptime(
                r.groups()[0].strip() + " " + r.groups()[1].strip()[:-1].replace(" ", ""),
                "%H:%M:%S GRB%y%m%d",
            ).strftime("%Y-%m-%dT%H:%M:%S")
    else:
        print(T)

    return d


@workflow
def gcn_meta(gcntext: GCNText):  # ->
    d = {}

    for c in "DATE", "SUBJECT", "NUMBER":
        r = re.search(c+":(.*)", gcntext)
        if r is not None:
            d[c] = r.groups()[0].strip()

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

    if r is not None:
        grb_name = r.groups()[0].strip().replace(" ","")

        return dict(mentions_named_grb=grb_name)
    else:
        return {}

@workflow
def gcn_lvc_event(gcntext: GCNText):  # ->
    D = {}

    r = re.search("SUBJECT: *(LIGO/Virgo.*?):", gcntext, re.I)

    if r is not None:
        D['lvc_event'] = r.groups()[0].strip()
    
        r = re.search(r"at (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d*?) UTC",
                       re.sub(r"[ \n\r]+", " ", gcntext),
                       re.I)

        if r is not None:
            D['lvc_event_utc'] = r.groups()[0].strip()


    return D

@workflow
def gcn_integral_lvc_countepart_search(gcntext: GCNText):  # ->
    r = re.search("SUBJECT: *(LIGO/Virgo.*?):.*INTEGRAL", gcntext, re.I)

    D = {}

    if r is not None:
        original_event = r.groups()[0].strip()

        D['original_event']=original_event
    
    r_u = re.search(
            r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:[\d\.]+?) UTC, hereafter T0", gcntext)

    if r_u is not None:
        D['original_event_utc'] = r_u.groups()[0].strip()

    return D


@workflow
def gcn_integral_countepart_search(gcntext: GCNText):  # ->

    r = re.search("SUBJECT:(.*?):.*counterpart.*INTEGRAL", gcntext, re.I)

    if r is None:
        r = re.search("SUBJECT:(.*?):.*INTEGRAL.*counterpart.*", gcntext, re.I)

    if r is None:
        r = re.search("SUBJECT:(.*?):.*associated.*INTEGRAL.*", gcntext, re.I)

    r_u = re.search(
            r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:[\d\.]+?) UTC, hereafter T0", gcntext)

    if r is not None and r_u is not None:
        original_event = r.groups()[0].strip()
        original_event_utc = r_u.groups()[0].strip()

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

    return {}


@workflow
def gcn_icecube_circular(gcntext: GCNText):  # ->
    r = re.search("SUBJECT:(.*?)- IceCube observation of a(.*)",
                  gcntext, re.I)

    if r is not None:
        ev, descr = r.groups()

        return dict(
                    reports_icecube_event=ev.strip(),
                    icecube_event_descr=descr.strip(),
                )
    return {}


@workflow
def gcn_lvc_circular(gcntext: GCNText):  # ->
    r = re.search("SUBJECT:.*?(LIGO/Virgo .*?): Identification",
                  gcntext, re.I)
    
    if r is not None:
        return dict(lvc_event_report=r.groups()[0].strip())

    return {}


@workflow
def integral_ul_old_variation(gcntext: GCNText):
    r = re.search("upper limit .*? ([\d\.e\-]*?) erg/cm.*? for a 1 s duration", 
                   re.sub(r"[ \n\r]+", " ", gcntext))
    
    if r is None:
        r = re.search("We find a limiting fluence of ([\d\.e\-]*?) erg/cm", 
                   re.sub(r"[ \n\r]+", " ", gcntext), re.I)
    
    if r is None:
        r = re.search("([\d\.e\-]*?) erg/cm2 for 1 s", 
                   re.sub(r"[ \n\r]+", " ", gcntext))
    
    if r is None:
        r = re.search("limiting peak flux is ~([\d\.e\-\^x]*?) erg/cm.*? at 1 s time scale",
                   re.sub(r"[ \n\r]+", " ", gcntext))

    if r is not None:
        return dict(
                    integral_ul=float(r.groups()[0].strip().replace("x10^","e")),
                )
    return {}


@workflow
def integral_ul(gcntext: GCNText):
    r = re.search("upper limit on the 75-2000 keV fluence of ([\d\.e\-\^x]*?) *?erg/cm", 
                   re.sub(r"[ \n\r]+", " ", gcntext))

    if r is not None:
        return dict(
                    integral_ul=float(r.groups()[0].strip().replace("x10^","e")),
                )
    return {}





@workflow
def gcn_grb_integral_circular(gcntext: GCNText):  # ->
    r = re.search("SUBJECT:.*?(GRB.*?):.*INTEGRAL.*",
                  gcntext, re.I)

    r_t = re.search(r"(\d\d:\d\d:\d\d) +UT",
                        gcntext, re.I)

    if r is not None and r_t is not None:
        grbname = r.groups()[0].strip()
        grbtime = r_t.groups()[0].strip()

        date = grbname.replace("GRB", "").strip()
        utc = "20" + date[:2] + "-" + date[2:4] + "-" + date[4:6] + " " + grbtime

        return dict(integral_grb_report=grbname, event_t0=utc)
    return {}


@workflow
def gcn_lvc_integral_counterpart(gcntext: GCNText):  # ->
    r = re.search("SUBJECT:.*?(LIGO/Virgo .*?):.*INTEGRAL",
              gcntext, re.I)

    if r is not None:
        return dict(lvc_counterpart_by="INTEGRAL")

    return {}

@workflow
def submitter(gcntext: GCNText):
    r = re.search("FROM:(.*?)<(.*?)>\n", gcntext, re.M | re.S)

    if r is not None:
        return dict(
                    gcn_from_name=r.groups()[0].strip(),
                    gcn_from_email=r.groups()[1].strip(),
                )
    return {}

@workflow
def authors(gcntext: GCNText):
    text = re.sub("\r", "", gcntext)

    r = re.search("FROM:.*?\n\n(.*?)\n\n", text, re.M | re.S)

    if r is not None:
        return dict(
                    gcn_authors=r.groups()[0].replace("\n", " ").strip(),
                )
    return {}





if __name__ == "__main__":
    cli()
