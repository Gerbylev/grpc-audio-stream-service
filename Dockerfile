FROM python:3.11

COPY requirements.txt .
RUN pip install -r requirements.txt

WORKDIR /app

COPY src .

EXPOSE 5000

CMD ["python", "main.py"]
