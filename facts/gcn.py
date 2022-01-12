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
from colorama import Fore, Style
from facts import common
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
    return common.mentions_keyword("", gcntext)


@workflow
def mentions_named(entry: GCNText):  # ->
    return common.mentions_grblike("", entry)


@workflow
def fermi_realtime(gcntext: GCNText):  # ->$                                                                                                                                                                
    d = {} # type: typing.Dict[str, typing.Union[str, int]]

    r = re.search(r"At (.*?), the Fermi Gamma-ray Burst Monitor \(GBM\) triggered", gcntext)
    
    if r is not None:
        d['grb_isot'] = datetime.strptime(
                r.groups()[0].strip(), 
                "%H:%M:%S UT on %d %b %Y"
            ).strftime("%Y-%m-%dT%H:%M:%S")


    r = re.search(r"The on-ground calculated location, using the Fermi GBM trigger data.*?"
                  r"RA = (?P<ra>[\d\.\-\+]*?), Dec = (?P<dec>[\d\.\-\+]*?) .*?"
                  r"with a statistical uncertainty of (?P<rad>[\d\.\-\+]*?) degrees.",
                  gcntext
                  )

    if r is not None:
        d['gbm_ra'] = r.group('ra')
        d['gbm_dec'] = r.group('dec')
        d['gbm_rad'] = r.group('rad')

    return d

@workflow
def fermi_v2(gcntext: GCNText):  # ->$                                                                                                                                                                
    d = {} # type: typing.Dict[str, typing.Union[str, int]]

    r = re.search(r"At (?P<grb_date>[0-9:\.]*? UT on [0-9]{1,2} [a-zA-Z]*? [0-9]{4}?).*?, the Fermi Gamma-Ray Burst Monitor \(GBM\) triggered and located (?P<name>GRB [0-9]{6}[A-G])", 
                   re.sub("[ \n]+", " ", gcntext))
        
    if r is not None:
        d['grb_isot'] = datetime.strptime(
                r.group('grb_date').strip(), 
                "%H:%M:%S.%f UT on %d %B %Y"
            ).strftime("%Y-%m-%dT%H:%M:%S.%f")

    return d

@workflow
def gbm_balrog(gcntext: GCNText):  # ->$                                                                                                                                                                
    d = {} # type: typing.Dict[str, typing.Union[str, int]]

    r = re.search(r"(?P<url_json>https://.*?json)", gcntext)

    if r:
        d['url_json'] = r.group('url_json')
        d['url'] = d['url_json'].replace('/json', '/')

        j_data = requests.get(d['url_json']).json()

        d['grb_isot'] = j_data[0]['grb_params'][0]['trigger_timestamp'].replace("Z", "")
        d['gbm_trigger_id'] = int(j_data[0]['grb_params'][0]['trigger_number'])
        d['balrog_ra'] = j_data[0]['grb_params'][0]['balrog_ra']
        d['balrog_ra_err'] = j_data[0]['grb_params'][0]['balrog_ra_err']
        d['balrog_dec'] = j_data[0]['grb_params'][0]['balrog_dec']
        d['balrog_dec_err'] = j_data[0]['grb_params'][0]['balrog_dec_err']
    
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
def swift_trigger_id(gcntext: GCNText):  # ->$                                                                                                                                                                
    d = {} # type: typing.Dict[str, typing.Union[str, int]]

    T = re.sub("\n", " ", gcntext, re.M | re.S)
    r = re.search(r"SUBJECT: .*?Swift detection", 
                  T)
    
    if r is not None:
        r_t = re.search('trigger=([0-9]+)', T)
        if r_t is not None:
            d['swift_trigger_id'] = int(r_t.group(1))
            d['detected_by'] = "swift"
    
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
    r = re.search("SUBJECT:(.*?) *?:?-? *?IceCube observation of a(.*)",
                  gcntext, re.I)

    d = {}

    if r is not None:
        ev, descr = r.groups()

        d = dict(
                    **d,
                    reports_icecube_event=ev.strip(),
                    reports_event=ev.strip(),
                    icecube_event_descr=descr.strip(),
                )

        #TODO: should be able to common URLs and re-use

        r_notice_url = re.search("(https://gcn.gsfc.nasa.gov/.*?\.amon)", gcntext)

        if r_notice_url is not None:
            gcn_notice_block_text = requests.get(r_notice_url.group(1)).text

            notice_sep = "//////////////////////////////////////////////////////////////////////"
            for gcn_notice_text in gcn_notice_block_text.split(notice_sep):
                for line in gcn_notice_text.split('\n'):
                    k = line[:18].strip().strip(":").lower()
                    raw_v = line[18:].strip()
                    if k != "":                      
                        v = raw_v

                        r_deg = re.match(r"^([\d\.+\-]*?)d", raw_v)                    
                        if r_deg:
                            v = float(r_deg.group(1))

                        if k == "discovery_date":
                            r_date = re.search(r"(\d{2}/\d{2}/\d{2}) \(yy/mm/dd\)", raw_v)
                            if r_date:                        
                                v = r_date.group(1)
                                k = 'date_ymd'
                            else:
                                raise RuntimeError

                        if k == "discovery_time":
                            r_time = re.search(r"\{(\d{2}:\d{2}:[\d\.]+)\} UT", raw_v)
                            if r_time:                        
                                v = r_time.group(1)
                                k = 'time_hms'
                            else:
                                raise RuntimeError

                        d[f'amon_gcn_notice_{k}'] = v
        else:
            r_t = re.search(r'On (?P<date_time>\d{4}[/\- ]\d{2}[/\- ]\d{2} at \d{2}:\d{2}:[\d\.]*?) UT IceCube',
                        gcntext
                    )                

            if r_t:
                d['event_isot'] = datetime.strptime(
                        r_t.group('date_time').strip().replace("-", "/"), 
                        "%Y/%m/%d at %H:%M:%S.%f"
                    ).strftime("%Y-%m-%dT%H:%M:%S.%f")

            r_ra = re.search(r'RA: (?P<ra>[\d\.\-\+]*?) ',
                    gcntext
                    )

            if r_ra is not None:
                d['icecube_ra'] = r_ra.group('ra')
                d['event_ra'] = r_ra.group('ra')
            
            r_dec = re.search(r'Dec: (?P<dec>[\d\.\-\+]*?) ',
                    gcntext
                    )

            if r_dec is not None:
                d['icecube_dec'] = r_dec.group('dec')

        if 'icecube_ra' in d and 'icecube_dec' in d:
            d['event_ra'] = d['icecube_ra']
            d['event_dec'] = d['icecube_dec']
            
        if 'amon_gcn_notice_src_ra' in d and 'amon_gcn_notice_src_dec' in d:
            d['event_ra'] = d['amon_gcn_notice_src_ra']
            d['event_dec'] = d['amon_gcn_notice_src_dec']
        
        if 'amon_gcn_notice_time_hms' in d and 'amon_gcn_notice_date_ymd' in d:
            d['event_isot'] = datetime.strptime(
                        d['amon_gcn_notice_date_ymd'] + " " + d['amon_gcn_notice_time_hms'], 
                        "%y/%m/%d %H:%M:%S.%f"
                    ).strftime("%Y-%m-%dT%H:%M:%S.%f")
        

    return d


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
def clearly_detected_afterglow(gcntext: GCNText):
    text = re.sub(r"[ \n\r]+", " ", gcntext)
    if re.search("clearly detected", text) and re.search("afterglow", text):
        return dict(
                    reports_characteristic='http://odahub.io/ontology/afterglow',
                )
    return {}


@workflow
def afterglow(gcntext: GCNText):
    text = re.sub(r"[ \n\r]+", " ", gcntext)
    if re.search("afterglow", text):
        return dict(
                    reports_characteristic='http://odahub.io/ontology/afterglow',
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
def gcn_hawc(gcntext: GCNText):  # ->
    r = re.search(r"SUBJECT:.*?\b(HAWC[\- ]?[0-9]+?[A-Z]?)\b",
                  gcntext, re.I)

    d = {}

    if r is not None:
        ev = r.group(1)

        d = dict(
                    **d,
                    reports_hawc_event=ev.strip(),
                    reports_event=ev.strip(),
                )

        r_t = re.search(r'On (?P<date_time>\d{2} \d{2}, \d{4}, at \d{2}:\d{2}:[\d\.]{2,}) UTC',
                  gcntext
                )

        if r_t:
            d['grb_isot'] = datetime.strptime(
                    r_t.group('date_time').strip(), 
                    "%m %d, %Y, at %H:%M:%S.%f"
                ).strftime("%Y-%m-%dT%H:%M:%S.%f")
            d['event_isot'] = d['grb_isot']

        r_ra = re.search(r'RA.*?: (?P<ra>[\d\.\-\+]*?) ',
                  gcntext
                )

        if r_ra is not None:
            d['hawc_ra'] = float(r_ra.group('ra'))
            d['event_ra'] = float(r_ra.group('ra'))
        
        r_dec = re.search(r'Dec.*?: (?P<dec>[\d\.\-\+]*?) ',
                  gcntext
                )

        if r_dec is not None:
            d['hawc_dec'] = float(r_dec.group('dec'))
            d['event_dec'] = float(r_dec.group('dec'))
        

    return d


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

