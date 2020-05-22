FROM    python:3

WORKDIR /usr/src/app

RUN pip install poetry
COPY poetry.lock pyproject.toml ./
RUN poetry config virtualenvs.create false \
  && poetry install --no-interaction --no-ansi

COPY . .
RUN poetry install
