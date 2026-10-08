# Эксплуатация систем машинного обучения — лабораторные

Соловьёв Егор Юрьевич, М4206. Уникальный префикс ресурсов: `esolovev`.

Решения основаны на оригинальных `ml-service.zip` и `practice2-deploy-search-driver.zip`. Общий pipeline находится в `.github/workflows/ci-cd.yml`.

## Лабораторная 1: Iris

Исправлены путь к модели, ссылка на ConfigMap, selector Deployment, selector Service, readiness endpoint и targetPort. Все имена и labels согласованы и используют `esolovev-iris`. В CI приложение проверяется на всех трёх классах Iris; кластерный деплой использует неизменяемый digest опубликованного образа.

```bash
cd lab1
python train.py
python scripts/check_api.py
```

## Лабораторная 2: Runbook Search

Исправлена передача проверенного индекса из builder в runtime. Helm принимает только `repository@sha256:<64 hex>` и передаёт этот digest в `/meta`. Quality gate сохраняет оба отчёта и требует подтверждённого отказа reverse-кандидату. Внешний smoke проверяет качество поиска, request ID, версию индекса, окружение и digest.

```bash
cd lab2
python scripts/build_index.py --output artifacts
python -m pytest -q
python scripts/check_quality.py
python scripts/check_chart.py
docker compose -p itmo-esolovev up -d --build search
python scripts/smoke_local.py
```

## CI/CD и сдача

Pipeline проверяет обе лабораторные, собирает и публикует:

- `ghcr.io/ingaleee/esolovev-iris:<commit>` (дополнительно `v1`);
- `ghcr.io/ingaleee/esolovev-search:<commit>`.

На push выполняются тесты, публикация образов и полная проверка обеих работ в отдельном Kubernetes внутри CI: staging, production, отрицательный smoke и настоящий rollback. Эти результаты сохраняются в artifact `local-kubernetes-integration`. Этот кластер временный и не является учебным стендом преподавателя.

Для учебного кластерного этапа запустите workflow вручную с `deploy=true`, после настройки секрета и публичности контейнеров. Для controlled rollback оставьте `demonstrate_rollback=true`.

Перед первым деплоем:

1. Получить актуальный kubeconfig преподавателя. В публичный репозиторий его не добавлять.
2. Сохранить base64 содержимого в Actions secret `KUBE_CONFIG_B64`.
3. Сделать контейнеры GHCR публичными, чтобы учебный кластер мог их скачивать.
4. Настроить environment `production`: Required reviewers — владелец репозитория; обход protection администратором отключён. После успешного staging человек одобряет production.

Все deployment jobs сериализованы. Releases: `esolovev-search-staging` и `esolovev-search-prod`, namespace `mlops-students`, `HELM_DRIVER=configmap`. Production получает тот же digest, который прошёл staging, без пересборки. Неправильное ранжирование приводит к провалу semantic smoke, откату на последнюю рабочую revision и повторной проверке. Затем нормальная версия повторно выпускается, чтобы оба окружения имели одинаковый digest. Release при откате не удаляется.

В CI artifacts сохраняются отчёты качества, metadata индекса, digest образов, `/meta`, Deployment JSON, Helm history и логи отрицательного smoke/rollback. Для преподавателя нужны URL репозитория и полного успешного deployment run.

**Почему readiness недостаточно:** readiness проверяет загрузку индекса и готовность процесса принимать запросы. При `rankingMode=reverse` процесс и probes здоровы, но релевантность результатов испорчена. Ошибку ловит semantic smoke по ожидаемому документу `doc-rollback`, после чего pipeline восстанавливает предыдущую рабочую revision.

## Состояние учебного стенда

8 октября 2026 преподаватель объявил перенос стенда. Выданный конфиг с прежним адресом API не отвечает. Локальные проверки и CI build не заменяют приёмку на учебном Kubernetes: полный deployment run нужно выполнить после выдачи рабочего доступа. Никакие результаты локального кластера не выдаются за сдачу на учебном стенде.

Исходные задания: `lab1/ASSIGNMENT.md` и `lab2/README.md`.
