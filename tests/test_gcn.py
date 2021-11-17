import logging

logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger()

def parse_gcn(i):
    import facts.gcn as g
    import facts.core as c

    G = g.gcn_source(i)
    F = c.workflows_for_input(dict(arg=G, arg_type=g.GCNText), output='dict')
    logger.info(F)

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

def test_gbm_balrog():
    G = parse_gcn(30634)

    assert G['paper:grb_isot'].strip("\"") == "2021-08-12T16:47:01.010000"
    assert G['paper:gbm_trigger_id'] == "650479626"
    assert G['paper:url'].strip("\"") == "https://grb.mpe.mpg.de/grb/GRB210812699/"
    

def test_icecube():
    G = parse_gcn(31085)

    assert G['paper:event_isot'].strip("\"") == "2021-11-16T10:33:16.050000"
    assert "%.6lg" % float(G['paper:ra']) == "42.45"
    assert "%.6lg" % float(G['paper:dec']) == "0.15"
    