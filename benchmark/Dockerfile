FROM python:3.10-slim
RUN apt-get update
RUN apt-get install -y less git build-essential
COPY ./requirements.txt /aider/requirements.txt
COPY ./requirements/* /aider/requirements/
COPY pyproject.toml /aider/pyproject.toml
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r /aider/requirements.txt -r /aider/requirements/requirements-dev.txt
COPY . /aider
RUN pip install --no-cache-dir -e /aider[dev]
RUN git config --global --add safe.directory /aider
WORKDIR /aider
