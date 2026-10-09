# Iris ML-сервис

Готовое решение первой лабораторной. Полная исходная методичка — `ASSIGNMENT.md`. Ресурсы используют префикс `esolovev-iris` и namespace `mlops-students`.

## Локальная проверка

Python 3.12; из каталога `lab1`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python train.py
python -m pytest -q
python scripts/check_api.py
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`train.py` обучает заданный `RandomForestClassifier(n_estimators=50, random_state=42)` на исходном Iris без изменения задания. Проверка API принимает setosa, versicolor и virginica и отвергает неверные признаки. `/live` проверяет процесс, `/health` — загрузку модели. Переменные `MODEL_PATH` и `MODEL_VERSION` поддерживаются.

## Контейнер и публикация

```bash
export IMAGE=ghcr.io/ingaleee/esolovev-iris:v1
docker build -t "$IMAGE" .
docker run --rm --read-only --cap-drop=ALL --security-opt=no-new-privileges --cpus=.5 --memory=512m -p 127.0.0.1:18090:8000 "$IMAGE"
```

В другом терминале:

```bash
python scripts/check_api.py --base-url http://127.0.0.1:18090
```

GitHub Actions публикует образ с tag `v1` и tag commit, сохраняет digest, SBOM и provenance. Runtime содержит обученную модель и только runtime-зависимости, работает как UID/GID 10001. Публикация использует временный `GITHUB_TOKEN` с правом `packages:write` только в build job.

## Учебный Kubernetes

`k8s/app.yaml` содержит исправленные ConfigMap, Deployment и ClusterIP Service. `scripts/deploy_iris.sh` из корня репозитория заменяет tag на digest из сборки, выполняет server dry-run, apply и rollout, проверяет фактический Deployment image и запускает внешнюю проверку через localhost port-forward. Он сохраняет Deployment, ответы API и лог port-forward в `lab1/evidence/`.

Для учебного развёртывания запускается общий workflow с `deploy=true`; для временного CI-кластера этот же сценарий выполняется автоматически. Только API учебного кластера может подтвердить его RBAC и квоты; приёмку ставит преподаватель.

Раздел методички про `pass init` относится к ручному `docker login` на учебной Linux-ВМ. Его нужно отдельно подтвердить на ВМ; успешная публикация через `GITHUB_TOKEN` не является доказательством инициализации `pass` в домашней папке студента. Пароли, registry credentials и kubeconfig в Git не сохраняются.
