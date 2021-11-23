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


def parse_atel(i) -> dict:
    import facts.atel as a
    import facts.core as c

    G = None
    for _G in a.list_entries():
        if _G['atelid'] == str(i):
            G = _G
            break

    if G is None:
        raise RuntimeError

    F = c.workflows_for_input(dict(arg=G, arg_type=a.ATelEntry), output='dict')
    logger.info(f"workflows for input: {F}")

    for p, o in F.items():
        print(":", p, o)

    return F

def test_iul():
    G = parse_gcn(20249)

    assert float(G['paper:integral_ul'])  == 4.6e-7


def test_fermirt():
    G = parse_gcn(28702)

    assert G['paper:grb_isot'].strip("\"") == "2020-10-20T17:33:54"

def test_swift():
    G = parse_gcn(28666)

    assert G['paper:grb_isot'].strip("\"") == "2020-10-17T09:46:31"

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
    G = parse_gcn(31085)

    assert G['paper:reports_icecube_event'] == 'IceCube-211116A'
    assert G['paper:event_isot'].strip("\"") == "2021-11-16T10:33:16.050000"
    assert "%.6lg" % float(G['paper:icecube_ra']) == "42.45"
    assert "%.6lg" % float(G['paper:icecube_dec']) == "0.15"
    
    G = parse_gcn(30957)

    assert G['paper:reports_icecube_event'] == 'IceCube-211023A'
    assert G['paper:event_isot'].strip("\"") == "2021-10-23T08:31:18.310000"
    assert "%.6lg" % float(G['paper:icecube_ra']) == "253.3"
    assert "%.6lg" % float(G['paper:icecube_dec']) == "-1.72"
    

def test_learn_gcns():
    import facts.core
    import facts.gcn

    t = facts.core.workflows_by_input(1, input_types=[facts.gcn.GCNText])
    

def test_atel_long_frb_name():
    G = parse_atel(15055)

    assert G['paper:mentions_named_event'] == 'FRB20211122A'
    

def test_atel_pks():
    G = parse_atel(15058)

    assert G['paper:mentions_named_event'] == 'PKS0903-57'
    