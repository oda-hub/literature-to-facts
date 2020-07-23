import logging

logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger()

def test_gcns():
    import facts.gcn as g
    import facts.core as c

    G = g.gcn_source(20249)
    F = c.workflows_for_input(dict(arg=G, arg_type=g.GCNText))
    logger.info(F)

    for f in F[1]:
        print(":", f)


