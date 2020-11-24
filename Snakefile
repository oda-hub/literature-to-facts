import subprocess

tag=subprocess.check_output(["git", "describe", "--always", "--tags"]).decode().strip()
repo="odahub/facts"

rule build:
  input:
    "Dockerfile"

  shell:
    "docker build . -t {repo}:{tag}"
