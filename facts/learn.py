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
from facts.core import workflow
import facts.core
import facts.arxiv
import facts.gcn
from colorama import Fore, Style # type: ignore

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(threadName)s %(name)s %(message)s"
                    )

logger = logging.getLogger()




PaperEntry = typing.NewType("PaperEntry", dict)


@click.group()
@click.option("--debug", "-d", default=False, is_flag=True)
def cli(debug):
    if debug:
        logger.setLevel(logging.DEBUG)




@cli.command()
@click.option("--workers", "-w", default=1)
@click.option("-a", "--arxiv", is_flag=True, default=False)
@click.option("-g", "--gcn", is_flag=True, default=False)
def learn(workers, arxiv, gcn):
    it = []

    if arxiv:
        it.append(facts.arxiv.PaperEntry)
    
    if gcn:
        it.append(facts.gcn.GCNText)

    t = facts.core.workflows_by_input(workers, input_types=it)

    logger.info(f"read in total {len(t)}")

    open("knowledge.n3", "w").write(t)

@cli.command()
def publish():
    import odakb.sparql

    D = open("knowledge.n3").readlines()

    odakb.sparql.default_prefixes.append("\n".join([d.strip().replace("@prefix","PREFIX").strip(".") for d in D if 'prefix' in d]))

    odakb.sparql.insert(
                    ("\n".join([d.strip() for d in D if 'prefix' not in d])).encode('utf-8').decode('latin-1')
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
