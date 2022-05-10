# literature-to-facts

## How to contribute to literature analysis?

_prepared-for_: scienstists, contributors 

simply add a function following the example:

https://github.com/cdcihub/literature-to-facts/blob/master/facts/gcn.py#L134 

consider adding a test for your and our safety:

https://github.com/cdcihub/literature-to-facts/blob/master/tests/test_gcn.py

## Is this like google, finding keywords?

not really. It is extracting structured data, propositions, encoded in RDF. E.g. _GRBXXX is-detected-by Swift/BAT_.

It can also extract keywords, but unlike google, it, for the moment, uses fixed set of keywords.

see linked-data concept for mode ideas.

## Try it locally

for *ATels*:

Not all atels are ingested, only "interesting" ones (with some useful attributes).

Currently, there are 836 interesting ATels.

to parse atels from html:

```python
python -m  facts.atel -d parse-html ~/ATels.html
```

or fetch last ones:

```python
python -m  facts.atel -d fetch
```

to extract from atels
```python
python -m facts.learn learn -t
```


to extract from atels
```python
python -m facts.learn learn -t
```

it will store knowledge.n3

which is then published to the kb (given the permissions)

```python
python -m facts.learn publish
```

