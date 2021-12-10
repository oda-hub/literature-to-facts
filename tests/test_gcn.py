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


def parse_atel(i):
    import facts.atel as a
    import facts.core as c

    A = {int(v['atelid']):v for v in a.list_entries()}[i]
    F = c.workflows_for_input(dict(arg=A, arg_type=a.ATelEntry), output='dict')
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

    G = parse_gcn(31182)

    assert G['paper:swift_trigger_id'] == "1088376"


def test_atel_2sources():
    parse_atel(15100)