from collections import defaultdict
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


# def mentions_atel(title, body):  # ->$                                                                                                                                                                
#     pass

def mentions_grblike(title, body):  # ->$                                                                                                                                                                
    d = defaultdict(list) 

    for text in title, body:
        for pattern, name_format in [
                (r'\b(IceCube|IC|GRB|FRB|PKS|Mrk|HAWC)([ -]?)([0-9\.\-\+]{2,}[A-Z]?)\b', "{}{}{}"),
                (r'\b(AT) *?([0-9]{4}[a-z]{3})\b', "{}{}"),
                (r'\b(ZTF)([0-9]{2}[a-z]{7})\b', "{}{}")
            ]:
        
            for r in re.findall(pattern, text):
                if isinstance(r, str):
                    r = [r]

                full_name = name_format.format(*r).replace(' ', '')
                obj_kind_type = r[0]
                d['mentions_named_event'].append(full_name)
                d['mentions_named_event_type'].append(obj_kind_type)

                d[f'mentions_named_{obj_kind_type.lower()}'].append(full_name)
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