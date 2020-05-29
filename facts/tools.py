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
    ctx.invoke(facts.arxiv.fetch, n=200)
    ctx.invoke(facts.learn.learn, g=True, a=True)
    ctx.invoke(facts.learn.publish)

if __name__ == "__main__":
    cli()
