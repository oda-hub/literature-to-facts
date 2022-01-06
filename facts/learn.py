import logging
import typing
from concurrent import futures
import odakb.sparql # type: ignore
import re
import os
import json
import importlib
from datetime import datetime
import requests
import click
import rdflib # type: ignore
import time
import multiprocessing
import threading
from facts.core import workflow
import facts.core
import facts.arxiv
import facts.gcn
import facts.atel
from colorama import Fore, Style # type: ignore

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(threadName)s %(name)s %(message)s"
                    )

logger = logging.getLogger()




PaperEntry = typing.NewType("PaperEntry", dict)


@click.group()
@click.option("--debug", "-d", default=False, is_flag=True)
@click.option("-m", "--modules", multiple=True)
def cli(debug=False, modules=[]):
    if debug:
        logger.setLevel(logging.DEBUG)

    for module_name in modules:
        logger.info("loading additional module %s", module_name)
        mod = importlib.import_module(module_name)




@cli.command()
@click.option("--workers", "-w", default=1)
@click.option("-a", "--arxiv", is_flag=True, default=False)
@click.option("-g", "--gcn", is_flag=True, default=False)
@click.option("-t", "--atel", is_flag=True, default=False)
def learn(workers, arxiv, gcn, atel):
    it = []

    if arxiv:
        it.append(facts.arxiv.PaperEntry)
    
    if gcn:
        it.append(facts.gcn.GCNText)
    
    if atel:
        it.append(facts.atel.ATelEntry)

    t = facts.core.workflows_by_input(workers, input_types=it)

    logger.info(f"read in total {len(t)}")

    open("knowledge.n3", "w").write(t)

@cli.command()
def publish():

    D = open("knowledge.n3").read()

    odakb.sparql.LocalGraph.default_prefixes.append("\n".join([d.strip().replace("@prefix","PREFIX").strip(".") for d in D.splitlines() if 'prefix' in d]))

    D_g = D.split(".\n")

    logger.info("found knowledge, lines: %d fact groups %d", len(D.splitlines()), len(D_g))

    chunk_size = 1000
    
    for i in range(0, len(D_g), chunk_size):
        chunk_D = D_g[i:i + chunk_size]
        logger.info("chunk of knowledge, lines from %d .. + %d / %d", i, len(chunk_D), len(D_g))

        odakb.sparql.insert(
                        (".\n".join([d.strip() for d in chunk_D if 'prefix' not in d])).encode('utf-8').decode('latin-1')
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


@cli.command()
def parse_notices():
    # just swift for now

    fn = f"swift_grbs_{time.strftime(r'%Y%m%d%h')}.html"
    if os.path.exists(fn):
        page = open(fn).read()
    else:
        page = requests.get('https://gcn.gsfc.nasa.gov/swift_grbs.html').text
        with open(fn, "w") as f:
            f.write(page)


    col_names = None

    entries = []

    for row in re.findall("<tr.*?>(.*?)</tr>", page, re.S | re.M):
        
        if col_names is None:
            _col_names = []
            logger.info("col name row")
            for col in re.findall("<th.*?>(.*?)</th>", row, re.S | re.M):                
                _col_names.append(re.sub("[^a-z0-9]+", "_", col.lower()))
            if len(_col_names) > 2:
                col_names = _col_names
        else:        
            d = {}
            for i, col in enumerate(re.findall("<td.*?>(.*?)</td>", row, re.S | re.M)):
                d[col_names[i]] = re.sub("<.*?>", "", col)

            try:
                d['event_isot'] = "20" + d['date_yy_mm_dd'].replace('/', '-') + "T" + d['time_ut']
            except:
                logger.warning("problem with entry: %s", json.dumps(d, indent=4, sort_keys=True))
                continue

            entries.append(d)

    json.dump(entries, open('entries.json', "w"))

    G = rdflib.Graph()
    paper_ns = rdflib.Namespace('https://odahub.io/ontology/paper/')
    G.bind('paper', paper_ns)

    for entry in entries:
        
        entry_id = paper_ns[f"swift_notice_trigger_{entry['trig']}"]
        
        for k, v in entry.items():
            if k in [
                "bat_dec",
                "bat_error",
                "bat_ra",
                "date_yy_mm_dd",
                "event_isot",
                "time_ut",
                "trig",
                "xrt_dec",
                "xrt_error",
                "xrt_ra",
            ]:
                G.add((entry_id, paper_ns["swift_" + k], rdflib.Literal(v) ))

    with open("swift_notices.ttl", "w") as f:
        f.write(G.serialize(format='turtle'))




if __name__ == "__main__":
    cli()
