import re
import typing
import requests
import logging
import os

from facts.core import workflow
import facts.core
from facts.gcn import GCNText, NoSuchGCN, gcn_source

logger = logging.getLogger(__name__)


@workflow
def gcn_list_all() -> typing.List[GCNText]:

    from_gcn = int(os.environ.get("FROM_GCN", 27000))
    to_gcn = os.environ.get("TO_GCN", None)

    if to_gcn is None:
        gt = requests.get("https://gcn.gsfc.nasa.gov/gcn3_archive.html").text

        r = map(int, re.findall(r"<A HREF=gcn3/\d{1,5}.gcn3>(\d{1,5})</A>", gt))
        
        last_gcn = max(r)

        logger.debug(f"last_gcn {last_gcn}")
        to_gcn = last_gcn+1
    else:
        to_gcn = int(to_gcn)

    for i in reversed(range(from_gcn, to_gcn)):
        logger.debug(f"gcn: {i}")

        try:
            yield gcn_source(i)
        except NoSuchGCN:
            logger.warning(f"no GCN: {i}")




facts.core.workflow_context = [w for w in facts.core.workflow_context if w['name'] != 'gcn_list_recent' ]
