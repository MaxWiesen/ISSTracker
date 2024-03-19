FROM python:3.11.4 AS builder
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

FROM builder AS executor
WORKDIR /
COPY . /

CMD ["python", "iss_tracker.py"]

