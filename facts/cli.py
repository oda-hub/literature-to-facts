import click

from . import tools, learn, core, gcn, atel, arxiv

@click.group()
def cli():
    pass

cli.add_command(tools.cli, 'tools')
cli.add_command(learn.cli, 'learn')
cli.add_command(gcn.cli, 'gcn')
cli.add_command(atel.cli, 'atel')
cli.add_command(arxiv.cli, 'arxiv')


if __name__ == "__main__":
    cli()