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


if __name__ == "__main__":
    cli()
