# Лабораторная работа 1. Iris ML-сервис: от модели до Kubernetes

Методические указания для студентов. Цель — обучить модель, упаковать API в Docker-образ, опубликовать его в registry и развернуть в общем namespace кластера без помех другим участникам.

Рабочий каталог на учебной ВМ задаётся переменной окружения `$MLOPS_DIR` (путь уточните у преподавателя), например:

```bash
export MLOPS_DIR=...   # каталог с материалами курса
cd $MLOPS_DIR/lab1/ml-service
```

---

## 0. Что должно получиться

1. Локально работает API (`/health`, `/predict`).
2. Образ в Docker Hub (или другом registry): `docker.io/<DOCKERHUB_USER>/<ваш-префикс>-iris:v1`.
3. В namespace `mlops-students` созданы **свои** ConfigMap, Deployment и Service с уникальным префиксом.
4. Проверка через `kubectl port-forward` и `curl`.

Классы Iris: `0` — setosa, `1` — versicolor, `2` — virginica.

---

## Оценка

- Максимальный балл за лабораторную работу: **<уточняется>**.
- Срок сдачи сообщает преподаватель (дата/время дедлайна).
- При сдаче **не в срок** итоговый балл **уменьшается**

Критерии приёма — выполнение чеклиста в конце методички (работающий сервис в кластере, уникальные имена, корректные ответы API).

---

## 1. Доступ к кластеру (`.kube/config`)

kubectl по умолчанию читает конфигурацию из:

```text
~/.kube/config
```

Либо из путей в переменной `KUBECONFIG` (несколько файлов через `:`).

Проверка:

```bash
kubectl config current-context
kubectl config view --minify
kubectl -n mlops-students get pods
```

Ожидаемо: контекст учебного кластера (например `mlops-students`), пользователь с правами **только внутри** namespace `mlops-students`.

Важно:

- Создавать **namespaces** студентам обычно **нельзя** (`kubectl auth can-i create namespace` → `no`).
- Все объекты размещайте в `mlops-students`.
- Имена ресурсов должны быть **уникальными** (логин / фамилия / номер варианта), иначе вы затронете чужой Deployment/Service.

---

## 2. Docker credential store и `pass`

Без credential store Docker хранит логин/пароль в `~/.docker/config.json` в base64 — это небезопасно.

На учебной ВМ обычно уже настроен helper `docker-credential-pass` и в `~/.docker/config.json` указано:

```json
{
  "credsStore": "pass"
}
```

Helper хранит секреты в хранилище **pass** (GPG). Перед первым `docker login` нужно один раз инициализировать `pass`.

### 2.1. Самый простой `pass init` (учебная ВМ)

```bash
gpg --batch --passphrase '' --quick-gen-key \
  "docker@$(hostname) <$(whoami)@$(hostname)>" default default never

FPR=$(gpg --list-secret-keys --with-colons | awk -F: '/^fpr:/ {print $10; exit}')
pass init "$FPR"
pass ls
```

Для продакшена лучше ключ с passphrase; на учебной ВМ пустой passphrase допустим.

Проверка helper:

```bash
which docker-credential-pass
cat ~/.docker/config.json
```

Если `credsStore` ещё нет — добавьте `"credsStore": "pass"` в `~/.docker/config.json` (или попросите администратора ВМ).

---

## 3. Настройка Python-окружения

Для локальной работы с `train.py` и API рекомендуется использовать **[uv](https://docs.astral.sh/uv/)** — быстрый менеджер пакетов и виртуальных окружений для Python. На учебной ВМ `uv` обычно уже установлен system-wide; проверка: `uv --version`.

### 3.1. Рекомендуемый способ (`uv`)

```bash
cd $MLOPS_DIR/lab1/ml-service

# создать .venv и установить зависимости из requirements.txt
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

Дальше в этом же активированном окружении запускайте `python train.py` и `uvicorn` (см. следующий раздел).

Полезные команды:

```bash
uv --version
uv pip list
deactivate          # выйти из venv
```

### 3.2. Альтернатива (`venv` + `pip`)

Если `uv` недоступен:

```bash
cd $MLOPS_DIR/lab1/ml-service

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 4. Обучить модель и проверить API локально

Этот шаг совпадает с разделом 1 из `ml-service/README.md`: сначала обучение, затем проверка API на машине. Окружение должно быть уже настроено (раздел 3).

### 4.1. Что делает `train.py`

Скрипт обучает классификатор на датасете Iris и сохраняет модель рядом с собой:

1. Загружает `sklearn.datasets.load_iris`.
2. Обучает `RandomForestClassifier(n_estimators=50, random_state=42)` на всех данных.
3. Сохраняет результат в `model.joblib` через `joblib.dump`.

Отдельного train/test split в лабе нет — нужна готовая модель для сервиса. При сборке Docker-образа `train.py` также выполняется внутри Dockerfile.

### 4.2. Обучение и запуск API

```bash
cd $MLOPS_DIR/lab1/ml-service
source .venv/bin/activate   # если ещё не активировали

python train.py
# в каталоге ml-service появляется model.joblib

uvicorn app.main:app --host 127.0.0.1 --port 8000
```

API читает путь к модели из переменной окружения `MODEL_PATH` (по умолчанию `model.joblib`) и версию из `MODEL_VERSION` (по умолчанию `iris-v1`).

### 4.3. Проверка в другом терминале

```bash
curl -s http://127.0.0.1:8000/health

curl -s -X POST http://127.0.0.1:8000/predict \
  -H 'content-type: application/json' \
  -d '{"features":[5.1,3.5,1.4,0.2]}'
```

Ожидаемый ответ `/health` (модель загружена):

```json
{"status":"ready","model_version":"iris-v1"}
```

Ожидаемый ответ `/predict` для вектора setosa:

```json
{"class_id":0,"model_version":"iris-v1"}
```

Другие примеры векторов:

| Вектор | `class_id` | Класс |
|--------|------------|--------|
| `[5.1, 3.5, 1.4, 0.2]` | 0 | setosa |
| `[7.0, 3.2, 4.7, 1.4]` | 1 | versicolor |
| `[6.3, 3.3, 6.0, 2.5]` | 2 | virginica |

Эндпоинты для проверки: `/live`, `/health`, `/predict`. Смотрите реализацию в `app/main.py`.

---

## 5. Сборка образа (`docker build`)

Выберите **уникальное** имя приложения и свой Docker Hub login:

```bash
export APP_NAME=<ваш-префикс>-iris
export IMAGE=docker.io/<DOCKERHUB_USER>/$APP_NAME:v1

docker build -t "$IMAGE" .
docker run --rm -p 8000:8000 "$IMAGE"
```

Проверьте `/health` и `/predict` на `http://127.0.0.1:8000`, затем остановите контейнер (Ctrl+C / удалите контейнер).

---

## 6. Вход в registry (`docker login`)

```bash
docker login -u <DOCKERHUB_USER>
```

Пароль/токен будет сохранён через `pass` (если настроен `credsStore`).

Для Docker Hub удобнее Access Token (Account Settings → Security), а не пароль аккаунта.

Выход: `docker logout`.

---

## 7. Публикация образа (`docker push`)

```bash
docker push "$IMAGE"
```

Типичные ошибки:

| Сообщение | Причина |
|-----------|---------|
| `denied: requested access to the resource is denied` | не залогинены или нет прав на репозиторий |
| `unauthorized` | неверный логин/токен; повторите `docker login` |

После успешного push образ должен быть виден на hub.docker.com в вашем репозитории.

---

## 8. Kubernetes-манифест

Исходный шаблон: `ml-service/k8s/app.yaml`. В нём есть ошибки — отладьте манифест самостоятельно. Не мешайте в общем namespace остальным участникам команды: используйте **уникальные** имена ресурсов (логин / фамилия / номер варианта).

Рекомендуется сохранить итоговый файл отдельно, например:

```text
$MLOPS_DIR/lab1/lab1.yaml
```

Что сделать:

1. Заменить шаблонные имена на свои во всех объектах и labels.
2. Подставить свой образ вместо заглушки в Deployment.
3. Согласовать ссылки между объектами (ConfigMap ↔ Deployment, selector ↔ labels пода, Service ↔ поды).
4. Проверить, что probes, порты и переменные окружения соответствуют приложению (`app/main.py`, Dockerfile, локальный запуск).

### 8.1. Тип Service

Для отладки с вашей машины удобен `kubectl port-forward` к Service типа `ClusterIP` (см. ниже).

Если используете `NodePort`, учитывайте возможную квоту namespace и доступность IP нод. Список nodes студентам может быть недоступен.

Не копируйте чужие имена из `kubectl get deploy,svc` — работайте только со своим префиксом.

---

## 9. Проверка манифеста до запуска (`kubectl dry-run`)

```bash
# локальная проверка схемы API
kubectl apply --dry-run=client -f $MLOPS_DIR/lab1/lab1.yaml

# проверка на API-сервере (RBAC, квоты) без создания объектов
kubectl apply --dry-run=server -f $MLOPS_DIR/lab1/lab1.yaml
```

Если server dry-run ругается на NodePort и квоту — смените Service на `ClusterIP` и повторите.

Убедитесь, что имена свободны:

```bash
kubectl -n mlops-students get deploy,svc,cm | grep -E '<ваш-префикс>|NAME'
```

---

## 10. Применение и отладка (`kubectl apply`, `port-forward`)

### 10.1. Применить

```bash
kubectl apply -f $MLOPS_DIR/lab1/lab1.yaml

kubectl -n mlops-students get deploy,svc,pods \
  -l app.kubernetes.io/instance=<ваш-префикс>
```

Дождитесь `READY 1/1` у пода. Если ImagePullBackOff — проверьте имя образа и что репозиторий публичный (или настроен pull secret).

### 10.2. Port-forward (рекомендуемый способ отладки)

В одном терминале:

```bash
kubectl -n mlops-students port-forward svc/<ваш-префикс> 8000:80
```

В другом:

```bash
curl -s http://127.0.0.1:8000/health | jq .

curl -s -X POST http://127.0.0.1:8000/predict \
  -H 'content-type: application/json' \
  -d '{"features":[5.1,3.5,1.4,0.2]}' | jq .

curl -s -X POST http://127.0.0.1:8000/predict \
  -H 'content-type: application/json' \
  -d '{"features":[6.3,3.3,6.0,2.5]}' | jq .
```

Ожидаемо для virginica-вектора: `"class_id": 2`.

Альтернатива: `port-forward` на Deployment:

```bash
kubectl -n mlops-students port-forward deploy/<ваш-префикс> 8000:8000
```

(если пробрасываете напрямую в контейнер — порт `8000`, не `80`).

### 10.3. Диагностика

```bash
kubectl -n mlops-students describe pod -l app.kubernetes.io/instance=<ваш-префикс>
kubectl -n mlops-students logs -l app.kubernetes.io/instance=<ваш-префикс>
```

Частые симптомы:

| Симптом | Что проверить |
|---------|----------------|
| CrashLoop / не Ready | логи пода, probes, переменные окружения |
| ImagePullBackOff | имя образа, push, доступность registry |
| Service не отвечает | selector Service и labels пода, порты |
| Forbidden на apply | права и квоты namespace |

---

## 11. Чеклист сдачи

- [ ] `train.py` + локальный `uvicorn` работают
- [ ] Образ собран и запушен: `docker.io/<DOCKERHUB_USER>/<ваш-префикс>-iris:v1`
- [ ] `pass` инициализирован, `docker login` успешен
- [ ] Манифест с **уникальными** именами, без ошибок шаблона
- [ ] `kubectl apply --dry-run=server` без ошибок
- [ ] Объекты созданы в `mlops-students`
- [ ] Через `port-forward`: `/health` → ready, predict setosa → `0`, virginica → `2`

---

## 12. Краткая шпаргалка команд

```bash
# python (uv)
cd $MLOPS_DIR/lab1/ml-service
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt

# kube
kubectl config current-context
kubectl auth can-i create namespace

# pass + docker auth
pass init "$FPR"
docker login -u <DOCKERHUB_USER>

# image
export IMAGE=docker.io/<DOCKERHUB_USER>/<ваш-префикс>-iris:v1
docker build -t "$IMAGE" .
docker push "$IMAGE"

# k8s
kubectl apply --dry-run=server -f lab1.yaml
kubectl apply -f lab1.yaml
kubectl -n mlops-students port-forward svc/<ваш-префикс> 8000:80
```

Удачи. Не мешайте чужим Deployment/Service в общем namespace.
