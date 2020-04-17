FROM    python:2

WORKDIR /usr/src/app

RUN pip install fabric==1.14.1
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN python ./setup.py install
