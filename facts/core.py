from collections import defaultdict
import logging
import typing
import hashlib
from concurrent import futures
import re
import sys
import json
from datetime import datetime
import requests
import feedparser # type: ignore
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
def cli(debug=False):
    if debug:
        logger.setLevel(logging.DEBUG)

from typing import TypeVar

InputType = TypeVar('InputType')

def workflow_id(entry):
    input_type = entry['arg_type']
    input_value = entry['arg']

    default = "http://odahub.io/ontology/paper#problematic"+input_type.__name__+hashlib.sha224(repr(input_value).encode()).hexdigest()[:8]

    for w in workflow_context:
        logger.info('searching for identity %s', w)
        if input_type in w['signature'].values() and w['name'] == 'identity':
            try:
                return w['function'](input_value)
            except Exception as e:
                logger.debug('problem: %s', e)
                raise

    return default


def workflows_for_input(entry, output: str='list') -> typing.Union[dict, tuple, str]:
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

            if len(o) == 0:
                logger.debug(f"   {Fore.YELLOW} empty:  {Style.RESET_ALL} {c_id} {w['name']} {o}")
                continue
            else:
                logger.debug(f"   {Fore.GREEN} found:  {Style.RESET_ALL} {c_id} {w['name']} {o}")

            for k, v in o.items():
                if isinstance(v, list):
                    vs = v
                else:
                    vs = [v]

                for _v in vs:
                    # try:
                    #     _v = float(_v)
                    # except:
                    #     pass

                    _v = rdflib.Literal(_v).n3()

                    data = rdflib.URIRef(f'<{c_ns}#{c_id}>'), f'<{c_ns}#{k}>', f'{_v}'

                    facts.append(data)

        except Exception as e: 
            logger.debug(f"  {Fore.YELLOW} problem {Style.RESET_ALL} {repr(e)}")


    logger.info(f"{c_id} facts {len(facts)}")

    # valuable?
    if not any(['mentions' in (" ".join(f)) for f in facts]):
        logger.debug(f"paper {Fore.RED}not valuable{Style.RESET_ALL}: %s", [" ".join(f) for f in facts])
        return c_id, []

    if output == 'list':
        return c_id, [" ".join(f) for f in facts]
    
    if output == 'dict':
        D = defaultdict(list)
        for s, p, o in facts:
            D[p.replace("http://odahub.io/ontology/paper#", "paper:").strip("<>")].append(rdflib.util.from_n3(o).value)

        return {k: v[0] if len(v) == 1 else list(sorted(set(v))) for k, v in D.items()}

    if output == 'n3':
        G = rdflib.Graph()

        for s in facts:
            G.update(f'INSERT DATA {{ {" ".join(s)} }}')

        return G.serialize(format='n3').decode()

    raise Exception(f"unknown output {output}")


def workflows_by_input(nthreads=1, input_types=None, max_inputs=None):
    logger.info("searching for input list...")

    collected_inputs = []

    t0 = time.time()

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

        logger.info(f"{Fore.YELLOW} valid input generator for {Fore.MAGENTA} {larg.__name__} : {w['function']} {Style.RESET_ALL} {Style.RESET_ALL}")

        for i, arg in enumerate(w['function']()):
            collected_inputs.append(dict(arg_type=larg, arg=arg))
            logger.debug(f"{Fore.BLUE} input: {Fore.MAGENTA} {str(arg):.100s} {Style.RESET_ALL} {Style.RESET_ALL}")
         
        logger.info("collected %d arguments", len(collected_inputs))

        if max_inputs is not None and len(collected_inputs) > max_inputs:
            logger.warning(f"selecting only %s", max_inputs)
            break

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


    if False:
        D  ='INSERT DATA { '+" .\n".join(facts) + '}'
        logger.debug(D)
        try:
            G.update(D)
        except Exception as e:
            logger.error(f"problem {e}  adding \"{s}\"")
            raise Exception()
    else:
        for fact in facts:
            D  = f'INSERT DATA {{ {fact} }}'
            logger.info(D)
            try:
                G.update(D)
            except Exception as e:
                logger.error(f"problem {e}  adding \"{D}\"")
                raise Exception(f"problem {e}  adding \"{D}\"")

    r = G.serialize(format='n3')

    if isinstance(r, bytes):
        return r.decode()
    else:
        return r

if __name__ == "__main__":
    cli()
