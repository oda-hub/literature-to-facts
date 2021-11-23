import re
import typing
from facts.core import workflow


def relevant_keywords():
    # TODO: fetch from KG, cache with expiration
    return [ 
                "HAWC", "INTEGRAL", "CTA", "HESS", "MAGIC", "LST", "SKA",
                "IceCube", "LIGO/Virgo", "ANTARES", "Fermi/LAT",
                "SPI-ACS", "ISGRI",
                "FRB", "GRB", "magnetar", "SGR", "blazar"
                "GW170817", "GW190425", 
        ]


def mentions_grblike(title, body):  # ->$                                                                                                                                                                
    d = {} # type: typing.Dict[str, typing.Union[str, int]]    

    for text in title, body:
        for r in re.findall(r'\b(IceCube|IC|GRB|FRB|PKS|Mrk|HAWC)([ -]?)([0-9\.\-\+]{2,}[A-Z]?)\b', text):
            full_name = f"{r[0]}{r[1]}{r[2]}"
            d['mentions_named_event'] = full_name.replace(' ', '')
            d['mentions_named_event_type'] = r[0]

            d[f'mentions_named_{r[0].lower()}'] = full_name.replace(' ', '')
    
    return d

def mentions_keyword(title, body):  # ->$                                                                                                                                                                
    d = {} # type: typing.Dict[str, typing.Union[str, int]]    

    for keyword in relevant_keywords():
        k = keyword.lower()

        n = len(re.findall(keyword, body))        
        if n > 0:
            d['mentions_'+k] = "body"
        if n > 1:
            d['mentions_'+k+'_times'] = n


        nt = len(re.findall(keyword, title))        
        if nt > 0:
            d['mentions_'+k] = "title"
        if nt > 1:
            d['mentions_'+k+'_times'] = n


    return d