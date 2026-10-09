# Эксплуатация систем машинного обучения — лабораторные

Соловьёв Егор Юрьевич, М4206. Уникальный префикс ресурсов: `esolovev`.

Решения основаны на оригинальных `ml-service.zip` и `practice2-deploy-search-driver.zip`. Общий pipeline находится в `.github/workflows/ci-cd.yml`.

## Воспроизводимость и эксплуатационные проверки

Docker base image закреплён по digest; все runtime-зависимости, включая транзитивные, закреплены в requirements.lock. Pytest и HTTP-клиент входят только в builder/development. Actions закреплены полными SHA, checkout не сохраняет credentials. Сборка публикует SBOM и provenance вместе с образом; эти сведения описывают сборку и не заменяют проверку доверия к registry.

Оба контейнера работают как UID/GID 10001 с read-only filesystem, без повышения привилегий и без Kubernetes ServiceAccount token. Startup probe разрешает загрузку модели до запуска liveness. Число потоков BLAS ограничено с учётом CPU-квот.

Для общего учебного namespace каждый сервис имеет CPU request `100m` и limit `200m`. Три постоянных Pod суммарно требуют лимит `600m`; Helm test добавляет `50m`. Учебный RollingUpdate использует `maxSurge=0`, `maxUnavailable=1`: старая реплика освобождает квоту перед созданием новой, возможен короткий перерыв в обслуживании. Это осознанный компромисс для общего стенда с одной репликой; chart позволяет `maxSurge=1`, `maxUnavailable=0`, когда namespace имеет дополнительную ёмкость. Бюджет и стратегия выбраны после реальных отказов квоты `shared-budget` для исходного Search limit `750m` и второй реплики при upgrade. Delivery сохраняет ошибки квот и не изменяет чужие ресурсы.

Для разработки установите `pip install -r lab2/requirements-dev.txt` в Python 3.12.15. Эти зависимости подходят обеим лабораторным. В CI сохраняются JUnit-отчёты, metadata индекса, отчёты качества и доказательства развёртывания.

CI проверяет runtime lock-файлы через `pip-audit` в отдельном окружении и сохраняет JSON-отчёт; известная уязвимость останавливает pipeline. FastAPI/Starlette обновлены до совместимых исправленных версий. Этот аудит проверяет опубликованные advisory для Python-пакетов, а не отсутствие любых возможных уязвимостей в системе.

## Лабораторная 1: Iris

Исправлены путь к модели, ссылка на ConfigMap, selector Deployment, selector Service, readiness endpoint и targetPort. Все имена и labels согласованы и используют `esolovev-iris`. В CI приложение проверяется на всех трёх классах Iris; кластерный деплой использует неизменяемый digest опубликованного образа.

```bash
cd lab1
python train.py
python -m pytest -q
python scripts/check_api.py
```

## Лабораторная 2: Runbook Search

Исправлена передача проверенного индекса из builder в runtime. Helm принимает только `repository@sha256:<64 hex>` и передаёт этот digest в `/meta`. Quality gate сохраняет оба отчёта и требует подтверждённого отказа reverse-кандидату. Внешний smoke проверяет качество поиска, request ID, версию индекса, окружение и digest.

Версия индекса зависит от канонического корпуса, параметров модели и версий научных библиотек. Перед десериализацией проверяется SHA-256 artifact, затем схема metadata, размерности и нормировка векторов. Artifact доверенный, собран внутри image: checksum обнаруживает повреждение, но не делает загрузку чужого pickle безопасной. Повторная сборка индекса должна давать те же metadata и checksum.

Сходство вычисляется как cosine similarity после общей L2-нормировки word/char-вектора; ties разрешаются стабильно. Рекомендации исключают исходный документ в обоих режимах. API отклоняет пустые запросы, ошибочные limits и лишние поля; слишком длинный или некорректный request ID заменяется безопасным новым ID. Iris отклоняет нечисловые и бесконечные признаки, а также значения вне диапазона float32, используемого классификатором. Ошибки валидации возвращают 422 без отражения пользовательского input, в том числе для нештатных JSON NaN/Infinity.

В исходном задании поле `recall_at_3` фактически означает долю запросов с хотя бы одним релевантным результатом. Этот контракт и его порог сохранены; отчёт дополнительно содержит явно названный `hit_rate_at_3` и настоящий `macro_recall_at_3`. MRR в задании ограничен top-3; определение записано в отчёте. Evaluation set не изменяется и не используется при обучении.

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

Перед upgrade предыдущая revision проверяется через API и сохраняется вместе с digest/build/index. Внешняя проверка кандидата оценивает весь контрольный набор, сверяет фактический Deployment и `/meta`, проверяет рекомендации, ошибки ввода и метрики. После rollback требуется точное совпадение предыдущих digest, build revision и index version. Ошибка транспорта или metadata не считается успешной демонстрацией плохого качества: отрицательный сценарий принимает только причину `semantic_quality`. Port-forward получает свободный localhost-порт и ограниченное время завершения; его лог сохранён.

В CI artifacts сохраняются отчёты качества, metadata индекса, digest образов, `/meta`, Deployment JSON, Helm history и логи отрицательного smoke/rollback. Для преподавателя нужны URL репозитория и полного успешного deployment run.

**Почему readiness недостаточно:** readiness проверяет загрузку индекса и готовность процесса принимать запросы. При `rankingMode=reverse` процесс и probes здоровы, но релевантность результатов испорчена. Ошибку ловит semantic smoke по ожидаемому документу `doc-rollback`, после чего pipeline восстанавливает предыдущую рабочую revision.

## Состояние учебного стенда

8 октября 2026 преподаватель объявил перенос стенда. Выданный конфиг тогда не отвечал; при повторной проверке 9 октября API доступен, права на Deployment/ConfigMap в `mlops-students` подтверждены. Создание namespaces запрещено. Полный учебный deployment выполняется вручную через Actions с `deploy=true` и защищённым секретом. Техническая проверка и приёмка преподавателем учитываются отдельно.

Исходные задания: `lab1/ASSIGNMENT.md` и `lab2/README.md`.
