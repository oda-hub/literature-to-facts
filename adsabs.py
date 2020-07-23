import re
import typing
import requests
import logging
import os

from facts.core import workflow
import facts.core
from facts.gcn import GCNText, NoSuchGCN, gcn_source, gcn_meta

logger = logging.getLogger(__name__)


@workflow
def gcn_ads_data(gcntext: GCNText):

    m = gcn_meta(gcntext) 

    adstoken = open(os.path.join(os.environ.get("HOME"), ".adsabs-token")).read().strip()

    r = requests.get("https://api.adsabs.harvard.edu/v1/search/query",\
                            params={'q': f'title:"{m["SUBJECT"]}"', 'fl': 'title, author'},
                            headers={'Authorization': 'Bearer ' + adstoken})

    print("ads returns", r, r.text)

    docs = r.json()['response']['docs']

    assert len(docs) == 1

    doc = docs[0]

    return dict(
                gcn_authors="; ".join(doc['author'])
            )





