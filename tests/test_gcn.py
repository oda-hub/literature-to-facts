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


def test_gcns():
    G = parse_gcn(20249)

    assert float(G['paper:integral_ul'])  == 4.6e-7

