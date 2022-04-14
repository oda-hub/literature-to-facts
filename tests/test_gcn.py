import pytest
import logging

from facts.arxiv import list_entries

logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger()

def parse_gcn(i) -> dict:
    import facts.gcn as g
    import facts.core as c

    G = g.gcn_source(i)
    F = c.workflows_for_input(dict(arg=G, arg_type=g.GCNText), output='dict')
    logger.info(F)

    for p, o in F.items():
        print(":", p, o)

    return F


def parse_atel(i):
    import facts.atel as a
    import facts.core as c

    A = {int(v['atelid']):v for v in a.list_entries()}[i]
    F = c.workflows_for_input(dict(arg=A, arg_type=a.ATelEntry), output='dict')
    logger.info(F)

    return F

# def parse_atel(i) -> dict:
#     import facts.atel as a
#     import facts.core as c

#     G = None
#     for _G in a.list_entries():
#         if _G['atelid'] == str(i):
#             G = _G
#             break

#     if G is None:
#         raise RuntimeError

#     F = c.workflows_for_input(dict(arg=G, arg_type=a.ATelEntry), output='dict')
#     logger.info(f"workflows for input: {F}")

#     for p, o in F.items():
#         print(":", p, o)

#     return F

def test_iul():
    G = parse_gcn(20249)

    assert float(G['paper:integral_ul'])  == 4.6e-7


def test_fermirt():
    G = parse_gcn(28702)

    assert G['paper:grb_isot'].strip("\"") == "2020-10-20T17:33:54"


def test_swift():
    G = parse_gcn(28666)

    assert G['paper:grb_isot'].strip("\"") == "2020-10-17T09:46:31"

    G = parse_gcn(31182)

    assert G['paper:swift_trigger_id'] == 1088376




def test_gbm_v2():
    G = parse_gcn(30585)

    assert G['paper:grb_isot'].strip("\"") == "2021-08-01T13:57:18.600000"


def test_gbm_coord():
    G = parse_gcn(31077)

    assert G['paper:grb_isot'].strip("\"") == "2021-11-12T14:34:22"
    assert "%.5lg" % float(G['paper:gbm_ra']) == "138.4"
    assert "%.5lg" % float(G['paper:gbm_dec']) == "-2.5"
    assert "%.5lg" % float(G['paper:gbm_rad']) == "3"


def test_gbm_balrog():
    G = parse_gcn(30634) 

    assert G['paper:grb_isot'].strip("\"") == "2021-08-12T16:47:01.010000"
    assert G['paper:gbm_trigger_id'] == 650479626
    assert G['paper:url'].strip("\"") == "https://grb.mpe.mpg.de/grb/GRB210812699/"
    

def test_icecube():
    G = parse_gcn(31126)

    assert G['paper:reports_icecube_event'] == 'IceCube-211125A'
    assert G['paper:event_isot'].strip("\"") == "2021-11-25T06:22:21.550000"
    assert float(G['paper:event_ra']) == 43.59
    assert float(G['paper:event_dec']) == 22.5899
    

    G = parse_gcn(31085)

    assert G['paper:reports_icecube_event'] == 'IceCube-211116A'
    assert G['paper:event_isot'].strip("\"") == "2021-11-16T10:33:16.050000"
    assert float(G['paper:event_ra']) == 42.45
    assert float(G['paper:event_dec']) == 0.15
    
    G = parse_gcn(30957)

    assert G['paper:reports_icecube_event'] == 'IceCube-211023A'
    assert G['paper:event_isot'].strip("\"") == "2021-10-23T08:31:18.310000"
    assert float(G['paper:event_ra']) == 253.3
    assert float(G['paper:event_dec']) == -1.7199

    G = parse_gcn(31110)

    assert G['paper:reports_icecube_event'] == 'IceCube-211123A'
    assert G['paper:event_isot'].strip("\"") == "2021-11-23T14:25:22.600000"
    assert float(G['paper:event_ra']) == 265.5199
    assert float(G['paper:event_dec']) == 7.33


def test_icecube_follow_up():
    G = parse_gcn(31120)
    
    assert G['paper:mentions_named_event'] == ['IceCube-211123A']


@pytest.mark.skip(reason='long')
def test_learn_gcns():
    import facts.core
    import facts.gcn

    t = facts.core.workflows_by_input(1, input_types=[facts.gcn.GCNText], max_inputs=10)
    

def test_atel_long_frb_name():
    G = parse_atel(15055)

    assert G['paper:mentions_named_event'] == ['FRB20211122A']
    

def test_atel_pks():
    G = parse_atel(15058)

    assert G['paper:mentions_named_event'] == ['PKS0903-57']
    

def test_gbm_allnamed():
    G = parse_gcn(31102) 

    # todo: complete
    # assert G['paper:grb_isot'].strip("\"") == "2021-08-12T16:47:01.010000"
    # assert G['paper:gbm_trigger_id'] == 650479626
    # assert G['paper:url'].strip("\"") == "https://grb.mpe.mpg.de/grb/GRB210812699/"
    

def test_hawc():
    G = parse_gcn(31106) 

    assert G['paper:grb_isot'].strip("\"") == "2021-11-23T03:52:23.500000"
    assert G['paper:mentions_named_hawc'] == ["HAWC-211123A"]
    assert G['paper:hawc_ra'] == 34.12
    assert G['paper:hawc_dec'] == -8.05

    
def test_afterglow():
    G = parse_gcn(31373) 

    assert G['paper:mentions_named_grb'] == ["GRB220101A"]
    assert G['paper:reports_characteristic'] == ['http://odahub.io/ontology/afterglow']
    

def test_many_named():
    G = parse_gcn(31132) 

    assert G['paper:mentions_named_event'] == ['IC211125A', 'IceCube-211125A']
    

def test_atel_2sources():
    G = parse_atel(15100)

    assert G['paper:mentions_named_event'] == ['IceCube-170922A', 'IceCube-211208A', 'IceCube-2112108A', 'PKS0735+17']

    assert G['paper:topics'] == ['agn', 'blazar', 'neutrinos', 'optical', 'request for observations']

    assert G['paper:cites_atel_id'] == '15099'
    assert G['paper:cites_gcn_id'] == '31191'
    assert G['paper:cites'] == ['http://odahub.io/ontology/paper#atel15098',
                                'http://odahub.io/ontology/paper#atel15099',
                                'http://odahub.io/ontology/paper#gcn31191']
    

def test_gcn_tns():
    G = parse_gcn(31627)
    assert G['paper:mentions_named_event'] == ['AT2022cmc', 'ZTF22aaajecb']

    G = parse_gcn(31626)
    assert G['paper:mentions_named_event'] == ['AT2022cmc', 'GRB220211A', 'ZTF22aaajecb', 'ZTF22aaajecp']
