import time
import click

import facts.gcn
import facts.arxiv
import facts.learn

@click.group()
def cli():
    pass


@cli.command()
@click.option("-1", "--one-shot", is_flag=True)
@click.pass_context
def daily(ctx, one_shot):
    tasks = [
            {'name':'gcn.fetch_tar', 'f': lambda:ctx.invoke(facts.gcn.fetch_tar), 'period_s': 3600*8, 'last': 0},
            {'name':'arxiv.fetch', 'f': lambda:ctx.invoke(facts.arxiv.fetch, max_results=200), 'period_s': 3600*8, 'last': 0},
            {'name':'atel.fetch', 'f': lambda:ctx.invoke(facts.atel.fetch), 'period_s': 3600, 'last': 0},
            {'name':'learn', 'f': lambda:ctx.invoke(facts.learn.learn, gcn=True, arxiv=True, atel=True), 'period_s': 1800, 'last': 0},
            {'name':'publish', 'f': lambda:ctx.invoke(facts.learn.publish), 'period_s': 3600, 'last': 0},
        ]

    while True:
        now = time.time()
        for t in tasks:
            age = now - t['last']
            if age < t['period_s']:
                print(f"{t['name']}: age {age} < period {t['period_s']}: too early, will run in {t['period_s'] - age}")
            else:
                print(f"{t['name']}: age {age} > period {t['period_s']}: time to run, overdue by {-t['period_s'] +age}")
                t['f']()
                t['last'] = now

        if one_shot:
            break

        time.sleep(301)

if __name__ == "__main__":
    cli()
