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

import facts

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

from typing import TypeVar

InputType = TypeVar('InputType')

def workflow_id(entry):
    input_type = entry['arg_type']
    input_value = entry['arg']

    for w in workflow_context:
        if input_type in w['signature'].values() and w['name'] == 'identity':
            return w['function'](input_value)


def workflows_for_input(entry, output='list'):
    input_type = entry['arg_type']
    input_value = entry['arg']

    c_ns, c_id = workflow_id(entry).split("#")

    facts = []

    for w in workflow_context:
        logger.debug(f"{Fore.BLUE} {w['name']} {Style.RESET_ALL}")
        logger.debug(f"   has " + " ".join([f"{k}:" + getattr(v, "__name__","?") for k,v in w['signature'].items()]))

        if input_type not in w['signature'].values():
            logger.debug(f"   skipping, need " + getattr(input_type, "__name__","?"))
            continue

        try:
            o = w['function'](input_value)
                
            logger.debug(f"   {Fore.GREEN} found:  {Style.RESET_ALL} {c_id} {w['name']} {o}")

            for k, v in o.items():
                if isinstance(v, list):
                    vs = v
                else:
                    vs = [v]

                for _v in vs:
                    try:
                        _v = float(_v)
                    except:
                        pass

                    if isinstance(_v, float):
                        _v = "%.20lg" % _v
                    else:
                        _v = str(_v)
                        _v = re.sub(r"[\$\\\"]", "", _v)
                        _v = "\""+str(_v)+"\""

                    data = f'<{c_ns}#{c_id}> <{c_ns}#{k}> {_v}'

                    facts.append(data)

        except (AttributeError, ValueError) as e: 
            logger.debug(f"  {Fore.YELLOW} problem {Style.RESET_ALL} {repr(e)}")


    logger.info(f"{c_id} facts {len(facts)}")

    if len(facts)<5:
        return c_id, []

    print("\n".join(facts))

    if output == 'list':
        return c_id, facts

    if output == 'n3':
        G = rdflib.Graph()

        for s in facts:
            G.update(f'INSERT DATA {{ {s} }}')

        return G.serialize(format='n3').decode()

    raise Exception(f"unknown output {output}")


def workflows_by_input(nthreads=1, input_types=None):
    logger.info("searching for input list...")

    collected_inputs = []

    for w in workflow_context:
        logger.debug(f"{Fore.BLUE} {w['name']} {Style.RESET_ALL}")
        logger.debug(f"   has " + " ".join([f"{k}:" + getattr(v, "__name__","?") for k,v in w['signature'].items()]))
        r = w['signature'].get('return', None)
        largs = typing.get_args(r)

        if len(largs) == 0: 
            continue

        larg = largs[0]
        logger.debug(f"{Fore.GREEN} {larg} {Style.RESET_ALL}")

        if larg not in input_types:
            continue

        logger.info(f"{Fore.YELLOW} valid input generator for {Fore.MAGENTA} {larg.__name__} {Style.RESET_ALL} {Style.RESET_ALL}")

        for i, arg in enumerate(w['function']()):
            collected_inputs.append(dict(arg_type=larg, arg=arg))
            logger.debug(f"{Fore.BLUE} input: {Fore.MAGENTA} {str(arg):.100s} {Style.RESET_ALL} {Style.RESET_ALL}")
         
        logger.info(f"collected {i} arguments")

    t0 = time.time()
    logger.info(f"inputs search done in in {time.time()-t0}")


    Ex = futures.ThreadPoolExecutor

    r = []

    with Ex(max_workers=nthreads) as ex:
        for c_id, d in ex.map(workflows_for_input, collected_inputs):
            logger.debug(f"{c_id} gives: {len(d)}")
            r.append(d)

    facts = []
    for d in r:
        for s in d:
            facts.append(s)

    logger.info("updating graph..")

    G = rdflib.Graph()
    G.bind('paper', rdflib.Namespace('http://odahub.io/ontology/paper#'))

    print()

    if False:
        D  ='INSERT DATA { '+" .\n".join(facts) + '}'
        print(D)
        try:
            G.update(D)
        except Exception as e:
            logger.error(f"problem {e}  adding \"{s}\"")
            raise Exception()
    else:
        for fact in facts:
            D  = f'INSERT DATA {{ {fact} }}'
            print(D)
            try:
                G.update(D)
            except Exception as e:
                logger.error(f"problem {e}  adding \"{s}\"")
                raise Exception()

    return G.serialize(format='n3').decode()

if __name__ == "__main__":
    cli()
