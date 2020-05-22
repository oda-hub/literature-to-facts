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
                        _v = re.sub(r"[\$\\\"\n\r]", "", _v)
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


    if False:
        try:
            G.update('INSERT DATA { '+" .\n".join(facts) + '}')
        except Exception as e:
            logger.error(f"problem {e}  adding \"{s}\"")
            raise Exception()
    else:
        for fact in facts:
            logger.info(f"fact {repr(fact)}")
            try:
                G.update(f'INSERT DATA {{ {fact} }}')
            except Exception as e:
                logger.error(f'problem {e}  adding "{fact}"')
                raise 


    return G.serialize(format='n3').decode()


@cli.command()
@click.option("--workers", "-w", default=1)
def learn(workers):
    t = workflows_by_entry(workers)

    logger.info(f"read in total {len(t)}")

    open("knowledge.n3", "w").write(t)

@cli.command()
def publish():
    import odakb.sparql

    D = open("knowledge.n3").readlines()

    odakb.sparql.default_prefixes.append("\n".join([d.strip().replace("@prefix","PREFIX").strip(".") for d in D if 'prefix' in d]))

    odakb.sparql.insert(
                "\n".join([d.strip() for d in D if 'prefix' not in d])
                
            )


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
