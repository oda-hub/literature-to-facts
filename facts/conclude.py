import logging
import typing
from concurrent import futures
import re
import sys
import json
from datetime import datetime
import requests
import feedparser
import click
import rdflib # type: ignore
import time
import multiprocessing
import threading
from colorama import Fore, Style # type: ignore

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(threadName)s %(name)s %(message)s"
                    )

logger = logging.getLogger()




workflow_context = []

PaperEntry = typing.NewType("PaperEntry", dict)

def workflow(f):
    setattr(sys.modules[f.__module__], f.__name__[1:], f)
    workflow_context.append(dict(
                name=f.__name__, 
                function=f,
                signature=f.__annotations__,
            ))
    return f


@click.group()
@click.option("--debug", "-d", default=False, is_flag=True)
def cli(debug):
    if debug:
        logger.setLevel(logging.DEBUG)


class BoringPaper(Exception):
    "boring"




@cli.command()
@click.option("-s", "--search-string")
def fetch(search_string):
    r = requests.get('http://export.arxiv.org/api/query?search_query=all:' + search_string)
    json.dump(feedparser.parse(r.text), open("search.json", "w"))

@cli.command()
def fetch_recent():
    r = requests.get('http://arxiv.org/rss/astro-ph')
    json.dump(feedparser.parse(r.text), open("recent.json", "w"))

@workflow
def basic_meta(entry):  # ->

    return dict(location=entry['id'], title=entry['title'])


@workflow
def mentions_keyword(entry):  # ->
    d = {}

    for keyword in "INTEGRAL", "FRB", "GRB", "GW170817", "GW190425":
        k = keyword.lower()

        for field in 'title', 'summary':
            n = len(re.findall(keyword, entry[field]))
            if n>0:
                d['mentions_'+k] = field
            if n>1:
                d['mentions_'+k+'_times'] = n
        

    return d


def workflows(entry, output='n3', boring_limit=2):
    paper_id = entry['id'].split("/")[-1]
    paper_ns = 'http://odahub.io/ontology/paper#'

    facts = []

    for w in workflow_context:
        logger.debug(f"{Fore.BLUE} {w['name']} {Style.RESET_ALL}")
        logger.debug(f"   has {w['signature']}")

        #if not any((it is GCNText for it in w['signature'].values())):
        #    continue

        try:
            o = w['function'](entry)

            logger.debug(f"   {Fore.GREEN} found:  {Style.RESET_ALL} {paper_id} {w['name']} {o}")

            for k, v in o.items():
                if isinstance(v, list):
                    vs = v
                else:
                    vs = [v]

                for _v in vs:
                    if isinstance(_v, float):
                        _v = "%.20lg" % _v
                    else:
                        _v = str(_v)
                        _v = re.sub(r"[\$\\\"]", "", _v)
                        _v = "\""+str(_v)+"\""

                    data = f'<{paper_ns}arxiv{paper_id}> <{paper_ns}{k}> {_v}'

                    facts.append(data)

        except (AttributeError, ValueError) as e: 
            logger.debug(f"  {Fore.YELLOW} problem {Style.RESET_ALL} {repr(e)}")

    if len(list(facts)) <= boring_limit:
        raise BoringPaper

    logger.info(f"paper {paper_id} facts {len(facts)}")

    if output == 'list':
        return facts

    if output == 'n3':
        G = rdflib.Graph()

        for s in facts:
            G.update(f'INSERT DATA {{ {s} }}')

        return G.serialize(format='n3').decode()

    raise Exception(f"unknown output {output}")

def run_one_paper(entry):
    try:
        return entry['id'], workflows(entry, output='list')
    except BoringPaper:
        logger.debug(f"boring entry  {entry['id']}")

    return entry['id'], ""

def workflows_by_entry(nthreads=1):
    logger.info("reading...")
    t0 = time.time()
    entries=json.load(open("recent.json"))['entries']
    logger.info(f"reading done in {time.time()-t0}")


    Ex = futures.ThreadPoolExecutor
    #Ex = futures.ProcessPoolExecutor

    r = []

    with Ex(max_workers=nthreads) as ex:
        for paper_id, d in ex.map(run_one_paper, entries):
            logger.debug(f"{paper_id} gives: {len(d)}")
            r.append(d)

    facts = []
    for d in r:
        for s in d:
            facts.append(s)

    logger.info("updating graph..")

    G = rdflib.Graph()
    G.bind('paper', rdflib.Namespace('http://odahub.io/ontology/paper#'))

    try:
        G.update('INSERT DATA { '+" .\n".join(facts) + '}')
    except Exception as e:
        logger.error(f"problem {e}  adding \"{s}\"")
        raise Exception()

    return G.serialize(format='n3').decode()


@cli.command()
@click.option("--workers", "-w", default=1)
def learn(workers):
    t = workflows_by_entry(workers)

    logger.info(f"read in total {len(t)}")

    open("knowledge.n3", "w").write(t)


@cli.command()
def contemplate():
    G = rdflib.Graph()

    G.parse("knowledge.n3", format="n3")

    logger.info(f"parsed {len(list(G))}")

    s = []

    for rep_gcn_prop in "gcn:lvc_event_report", "gcn:reports_icecube_event":
        for r in G.query("""
                    SELECT ?c ?ic_d ?ct_d ?t0 ?instr WHERE {{
                            ?ic_g {rep_gcn_prop} ?c;
                                  gcn:DATE ?ic_d . 
                            ?ct_g ?p ?c;
                                  gcn:DATE ?ct_d;
                                  gcn:original_event_utc ?t0;
                                  gcn:instrument ?instr .
                        }}
                """.format(rep_gcn_prop=rep_gcn_prop)):

            if r[1] != r[2]:
                logger.info(r)
                s.append(dict(
                    event=str(r[0]),
                    event_gcn_time=str(r[1]),
                    counterpart_gcn_time=str(r[2]),
                    event_t0=str(r[3]),
                    instrument=str(r[4]),
                ))

    byevent = dict()

    for i in s:
        ev = i['event']
        if ev in byevent:
            byevent[ev]['instrument'].append(i['instrument'])
        else:
            byevent[ev] = i
            byevent[ev]['instrument'] = [i['instrument']]

    s = list(byevent.values())

    json.dump(s, open("counterpart_gcn_reaction_summary.json", "w"))

    s = []
    for r in G.query("""
                    SELECT ?grb ?t0 ?gcn_d WHERE {{
                            ?gcn gcn:integral_grb_report ?grb . 
                            ?gcn gcn:DATE ?gcn_d . 
                            ?gcn gcn:event_t0 ?t0 .
                        }}
                """):
        if r[1] != r[2]:
            logger.info(r)
            s.append(dict(
                event=str(r[0]),
                event_t0=str(r[1]),
                event_gcn_time=str(r[2]),
            ))

    json.dump(s, open("grb_gcn_reaction_summary.json", "w"))


if __name__ == "__main__":
    cli()
import logging
import typing
from concurrent import futures
import re
import sys
import json
from datetime import datetime
import requests
import click
import rdflib # type: ignore
from colorama import Fore, Style # type: ignore

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger()

workflow_context = []

GCNText = typing.NewType("GCNText", str)

def workflow(f):
    setattr(sys.modules[f.__module__], f.__name__[1:], f)
    workflow_context.append(dict(
                name=f.__name__, 
                function=f,
                signature=f.__annotations__,
            ))
    return f


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


def get_gcn_tag():
    logger.debug("https://gcn.gsfc.nasa.gov/gcn3/all_gcn_circulars.tar.gz")


@cli.command()
@workflow
def _gcn_list_recent():
    gt = requests.get("https://gcn.gsfc.nasa.gov/gcn3_archive.html").text

    r = re.findall(r"<A HREF=(gcn3/\d{1,5}.gcn3)>(\d{1,5})</A>", gt)

    logger.debug(f"results {len(r)}")

    for u, i in reversed(r):
        logger.debug(f"{u} {i}")


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
def gcn_meta(gcntext: GCNText):  # ->
    d = {}

    for c in "DATE", "SUBJECT":
        d[c] = re.search(c+":(.*)", gcntext).groups()[0].strip()

    return d


@workflow
def gcn_date(gcntext: GCNText) -> dict:  # date
    t = datetime.strptime(
        gcn_meta(gcntext)['DATE'], "%y/%m/%d %H:%M:%S GMT").timestamp()

    return dict(timestamp=t)


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


def gcn_workflows(gcnid: int, output='n3'):
    gs = gcn_source(gcnid)

    gcn_ns = 'http://odahub.io/ontology/gcn#'

    facts = []

    for w in workflow_context:
        logger.debug(f"{Fore.BLUE} {w['name']} {Style.RESET_ALL}")
        logger.debug(f"   has {w['signature']}")

        if not any((it is GCNText for it in w['signature'].values())):
            continue

        try:
            o = w['function'](gs)

            logger.debug(f"   {Fore.GREEN} found:  {Style.RESET_ALL} {gcnid} {w['name']} {o}")

            for k, v in o.items():
                if isinstance(v, list):
                    vs = v
                else:
                    vs = [v]

                for _v in vs:
                    if isinstance(_v, float):
                        _v = "%.20lg" % _v
                    else:
                        _v = "\""+str(_v)+"\""

                    data = '<{gcn_ns}gcn{gcnid}> <{gcn_ns}{prop}> {value}'.format(
                        gcn_ns=gcn_ns, gcnid=gcnid, prop=k, value=_v
                    )

                    facts.append(data)

        except (AttributeError, ValueError) as e: 
            logger.debug(f"  {Fore.YELLOW} problem {Style.RESET_ALL} {repr(e)}")

    if len(list(facts)) <= 3:
        raise BoringGCN

    logger.info(f"gcn {gcnid} facts {len(facts)}")

    if output == 'list':
        return facts

    if output == 'n3':
        G = rdflib.Graph()

        for s in facts:
            G.update(f'INSERT DATA {{ {s} }}')

        return G.serialize(format='n3').decode()

    raise Exception(f"unknown output {output}")

def run_one_gcn(gcnid):
    try:
        return gcnid, gcn_workflows(gcnid, output='list')
    except NoSuchGCN:
        logger.debug(f"no GCN {gcnid}")
    except BoringGCN:
        logger.debug(f"boring GCN {gcnid}")

    return gcnid, ""

def gcns_workflows(gcnid1, gcnid2, nthreads=1):
    G = rdflib.Graph()

    G.bind('gcn', rdflib.Namespace('http://odahub.io/ontology/gcn#'))

    with futures.ProcessPoolExecutor(max_workers=nthreads) as ex:
        for gcnid, d in ex.map(run_one_gcn, range(gcnid1, gcnid2)):
            logger.debug(f"{gcnid} gives: {len(d)}")
            for s in d:
                try:
                    G.update(f'INSERT DATA {{ {s} }}')
                except Exception as e:
                    logger.error(f"problem {e}  adding \"{s}\"")
                    raise Exception()

    return G.serialize(format='n3').decode()


@cli.command()
@click.option("--from-gcnid", "-f", default=1500)
@click.option("--to-gcnid", "-t", default=30000)
@click.option("--workers", "-w", default=1)
def learn(from_gcnid, to_gcnid, workers):
    t = gcns_workflows(from_gcnid, to_gcnid, workers)

    logger.info(f"read in total {len(t)}")

    open("knowledge.n3", "w").write(t)


@cli.command()
def contemplate():
    G = rdflib.Graph()

    G.parse("knowledge.n3", format="n3")

    logger.info(f"parsed {len(list(G))}")

    s = []

    for rep_gcn_prop in "gcn:lvc_event_report", "gcn:reports_icecube_event":
        for r in G.query("""
                    SELECT ?c ?ic_d ?ct_d ?t0 ?instr WHERE {{
                            ?ic_g {rep_gcn_prop} ?c;
                                  gcn:DATE ?ic_d . 
                            ?ct_g ?p ?c;
                                  gcn:DATE ?ct_d;
                                  gcn:original_event_utc ?t0;
                                  gcn:instrument ?instr .
                        }}
                """.format(rep_gcn_prop=rep_gcn_prop)):

            if r[1] != r[2]:
                logger.info(r)
                s.append(dict(
                    event=str(r[0]),
                    event_gcn_time=str(r[1]),
                    counterpart_gcn_time=str(r[2]),
                    event_t0=str(r[3]),
                    instrument=str(r[4]),
                ))

    byevent = dict()

    for i in s:
        ev = i['event']
        if ev in byevent:
            byevent[ev]['instrument'].append(i['instrument'])
        else:
            byevent[ev] = i
            byevent[ev]['instrument'] = [i['instrument']]

    s = list(byevent.values())

    json.dump(s, open("counterpart_gcn_reaction_summary.json", "w"))

    s = []
    for r in G.query("""
                    SELECT ?grb ?t0 ?gcn_d WHERE {{
                            ?gcn gcn:integral_grb_report ?grb . 
                            ?gcn gcn:DATE ?gcn_d . 
                            ?gcn gcn:event_t0 ?t0 .
                        }}
                """):
        if r[1] != r[2]:
            logger.info(r)
            s.append(dict(
                event=str(r[0]),
                event_t0=str(r[1]),
                event_gcn_time=str(r[2]),
            ))

    json.dump(s, open("grb_gcn_reaction_summary.json", "w"))


if __name__ == "__main__":
    cli()
