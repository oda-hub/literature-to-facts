tag=$(shell git describe --always --tags)
repo=odahub/facts
#repo=admin.reproducible.online/odahub-facts

dist:
	rm -fv dist/*
	python setup.py sdist

build: Dockerfile dist
	docker build . -t $(repo):$(tag)

push: build
	docker push $(repo):$(tag)

install: push
	helm upgrade --install facts chart --set image.tag=$(tag) --namespace default

run: build
	docker run $(repo):$(tag) python -m facts.tools daily
