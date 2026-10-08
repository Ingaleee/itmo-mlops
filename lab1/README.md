# Lab 1

## 1. Обучить модель и проверить API локально

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python train.py
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

В другом терминале:

```bash
curl -s http://127.0.0.1:8000/health
curl -s -X POST http://127.0.0.1:8000/predict \
  -H 'content-type: application/json' \
  -d '{"features":[5.1,3.5,1.4,0.2]}'
```

## 2. Собрать и опубликовать образ

Замените `REGISTRY_USER` и выберите уникальное имя:

```bash
export APP_NAME=s07-iris
export IMAGE=docker.io/REGISTRY_USER/$APP_NAME:v1
docker build -t "$IMAGE" .
docker run --rm -p 8000:8000 "$IMAGE"
docker push "$IMAGE"
```

# 3. Починить манифест
В манифесте есть ошибки, отладьте его и не мешайте в общем НС остальным членам команды. Публиковать сервис для отладки можно через node-port