import click

import facts.gcn
import facts.arxiv
import facts.learn

@click.group()
def cli():
    pass


@cli.command()
@click.pass_context
def daily(ctx):
    ctx.invoke(facts.gcn.fetch_tar)
    ctx.invoke(facts.arxiv.fetch, max_results=200)
    ctx.invoke(facts.atel.fetch)
    ctx.invoke(facts.learn.learn, gcn=True, arxiv=True, atel=True)
    ctx.invoke(facts.learn.publish)

if __name__ == "__main__":
    cli()
