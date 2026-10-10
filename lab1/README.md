# Лабораторная 1 — Iris Classifier

[Каталог проектов](../README.md) · [Окружение](../docs/development.md) · [CI/CD](../docs/delivery.md)

HTTP-сервис классификации Iris. Модель обучается на четырёх признаках цветка, сохраняется в артефакт и доставляется вместе с API в Docker-образе.

## Архитектура

```text
Iris dataset → RandomForest → model.joblib → Docker image → FastAPI → Kubernetes
```

`train.py` обучает `RandomForestClassifier(n_estimators=50, random_state=42)` на встроенном наборе Iris. API загружает модель при старте; readiness подтверждает её доступность. Multi-stage Docker-сборка выполняет обучение и тесты, затем переносит модель и runtime-зависимости в финальный образ.

| Каталог или файл | Назначение |
|---|---|
| `app/main.py` | API, загрузка модели и валидация запросов |
| `train.py` | Обучение и сохранение модели |
| `tests/` | Проверки модели и HTTP-контракта |
| `scripts/check_api.py` | Внешняя проверка работающего сервиса |
| `Dockerfile` | Сборка и непривилегированный runtime |
| `k8s/app.yaml` | ConfigMap, Deployment и ClusterIP Service |

## Локальный запуск

Подготовьте [окружение](../docs/development.md), затем выполняйте команды из `lab1/`.

```bash
python train.py
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Документация API: `http://127.0.0.1:8000/docs`.

## API

| Метод | Endpoint | Ответ |
|---|---|---|
| GET | `/live` | Процесс принимает запросы |
| GET | `/health` | Модель загружена, доступна её версия |
| POST | `/predict` | Класс цветка и версия модели |
| GET | `/docs` | OpenAPI UI |

`features` содержит ровно четыре конечных числа: длину и ширину чашелистика, длину и ширину лепестка. Неверный размер, bool, строки, NaN, Infinity, значения вне диапазона float32 и лишние поля отклоняются с 422.

```bash
curl -s http://127.0.0.1:8000/predict \
  -H 'Content-Type: application/json' \
  -d '{"features":[5.1,3.5,1.4,0.2]}'
```

```json
{"class_id":0,"model_version":"iris-v1"}
```

| `class_id` | Класс |
|---|---|
| 0 | setosa |
| 1 | versicolor |
| 2 | virginica |

## Проверки

```bash
python train.py
python -m pytest -q
python scripts/check_api.py
```

Для сервиса, запущенного отдельно:

```bash
python scripts/check_api.py --base-url http://127.0.0.1:8000
```

Проверяются readiness, все три класса и пять некорректных входов. Подтверждённые результаты: **18 тестов**, внешний API-контракт и развёртывание по digest — [отчёт](../docs/validation.md#iris-classifier).

## Docker

Команды выполняются из `lab1/`. Порт контейнера опубликован только на localhost.

```bash
docker build -t iris-api:local .
docker run --rm --name iris-api-local --read-only --cap-drop=ALL \
  --security-opt=no-new-privileges --cpus=.2 --memory=512m \
  -p 127.0.0.1:18090:8000 iris-api:local
```

В другом терминале:

```bash
python scripts/check_api.py --base-url http://127.0.0.1:18090
```

## Kubernetes

Общий [pipeline](../docs/delivery.md) публикует образ, подставляет digest в манифест и выполняет server dry-run, apply, rollout и внешний API-check. Оркестрация находится в [`scripts/deploy_iris.sh`](../scripts/deploy_iris.sh).

Ресурсы: `esolovev-iris-config`, `esolovev-iris` Deployment и Service в `mlops-students`. Runtime работает как UID/GID 10001, с read-only filesystem, без повышения привилегий и ServiceAccount token.

```bash
kubectl -n mlops-students port-forward --address=127.0.0.1 service/esolovev-iris 18090:80
```

В другом терминале, из `lab1/` с окружением лабораторной:

```bash
python scripts/check_api.py --base-url http://127.0.0.1:18090
```

## Конфигурация

| Переменная | Значение по умолчанию | Назначение |
|---|---|---|
| `MODEL_PATH` | `model.joblib` | Путь к доверенному артефакту модели |
| `MODEL_VERSION` | `iris-v1` | Версия в ответах API |

Модель десериализуется через joblib и должна поступать из доверенной сборки. Изменение пути не меняет версию автоматически.

Исходные требования сохранены в [ASSIGNMENT.md](ASSIGNMENT.md).
