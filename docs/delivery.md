# CI/CD и развёртывание

[Каталог проектов](../README.md) · [Разработка](development.md) · [Проверки](validation.md)

## Цепочка поставки

Основной workflow: [ITMO MLOps labs](../.github/workflows/ci-cd.yml).

```text
Тесты и качество → сборка и публикация → временный Kubernetes в CI
                                              ↓
                           staging → подтверждение → production
                                                        ↓
                                         semantic smoke → rollback
```

| Запуск | Что выполняется |
|---|---|
| Pull request | Тесты, сборка моделей, quality gate, аудит, Helm и сборка образов без публикации |
| Push в `main` | Те же проверки, публикация и интеграция в отдельном Kubernetes внутри CI |
| Ручной запуск с `deploy=true` | Дополнительно развёртывание Iris и Search staging, затем production после подтверждения |

При обычном push jobs `deploy-staging` и `promote-production` пропускаются по условию. Интеграция при этом проверяет staging, production и rollback во временном кластере. Развёртывание в постоянный кластер выбирается отдельным параметром.

## Публикуемые образы

| Сервис | Repository | Tags |
|---|---|---|
| Iris | `ghcr.io/ingaleee/esolovev-iris` | Commit SHA, дополнительно `v1` |
| Search | `ghcr.io/ingaleee/esolovev-search` | Commit SHA |

Tags позволяют найти сборку; Kubernetes получает `repository@sha256:digest`. Artifact `immutable-images` содержит digest каждого образа и build revision. Сборка сохраняет SBOM и provenance; базовый Python image и Actions закреплены неизменяемыми идентификаторами.

## Настройка кластера

| Параметр | Значение |
|---|---|
| Namespace | `mlops-students` |
| Префикс | `esolovev` |
| Helm storage driver | `configmap` |
| Secret | `KUBE_CONFIG_B64` |
| GitHub environments | `staging`, `production` |

Для доступа нужен kubeconfig с правами на собственные namespaced-ресурсы. Его base64-представление сохраняется только в Actions secret `KUBE_CONFIG_B64`. При запуске конфигурация восстанавливается во временный файл, проверяется с TLS и удаляется при завершении job.

Образы должны быть доступны кластеру для скачивания. Для `production` настройте required reviewer и отключите обход защиты администратором; deployment branch policy допускает `main`.

Pipeline создаёт только свои Deployment, Service, ConfigMap и Helm releases. Namespaces, CRD и общие ресурсы не создаются.

Для локальных команд Kubernetes выберите конфигурацию в текущем терминале:

```bash
export KUBECONFIG=/path/to/cluster.kubeconfig
export HELM_DRIVER=configmap
kubectl -n mlops-students auth can-i get deployments
```

## Запуск deployment

1. Открыть Actions → **ITMO MLOps labs** → **Run workflow**.
2. Выбрать `main` и включить `deploy`.
3. Для проверки отката оставить `demonstrate_rollback=true`.
4. Дождаться тестов, сборки и staging, затем подтвердить job в environment `production`.

Deployment jobs сериализованы общим concurrency group. Production использует digest из той же build job, который уже прошёл staging, без пересборки.

## Проверки релиза

Staging и production проходят Helm test и внешний API-check. Search проверяется на всём контрольном наборе: качество, рекомендации, request ID, ошибки ввода, метрики и идентичность Deployment/metadata.

До upgrade сохраняются последняя рабочая revision и её digest, build revision и index version. При провале проверки `helm rollback` восстанавливает эту revision; внешний smoke подтверждает точную версию и качество восстановленного сервиса.

Демонстрация выпускает reverse-кандидата, принимает только подтверждённый отказ `semantic_quality`, проверяет rollback и завершает normal promotion. Ошибка сети или несовпадение metadata останавливают сценарий.

## Ресурсы и runtime

Каждый сервис использует одну реплику, CPU request `100m` и limit `200m`. У Iris memory request/limit `128Mi/512Mi`, у Search — `256Mi/768Mi`. Runtime имеет UID/GID 10001, read-only filesystem, запрет повышения привилегий и отключённый ServiceAccount token.

При `maxSurge=0`, `maxUnavailable=1` обновление укладывается в квоту без дополнительного Pod и допускает короткий перерыв. Search chart поддерживает `maxSurge=1`, `maxUnavailable=0`, если кластер имеет ёмкость для второй реплики.

## Registry credentials

Docker может использовать `pass` как credential store: секрет хранится через GPG, а Docker config содержит `credsStore=pass` без embedded auth.

| Workflow | Назначение |
|---|---|
| [Iris registry credential store](../.github/workflows/registry-credentials.yml) | Проверка login, шифрования и cleanup в отдельной Linux-среде CI |
| [Temporary teaching registry access](../.github/workflows/teaching-registry-access.yml) | Зашифрованная передача временного `packages:read` токена выбранному публичному GPG-ключу для проверки login вне CI |

Второй workflow принимает публичный ключ и его fingerprint. Приватный ключ остаётся у получателя. После проверки выполняется logout, временный credential удаляется; зашифрованный artifact удаляется после использования. Время доступа ограничено job.

## Артефакты

| Actions artifact | Содержимое |
|---|---|
| `quality-and-contracts` | JUnit, normal/reverse quality reports, аудит и metadata индекса |
| `immutable-images` | Repository, digest и build revision |
| `local-kubernetes-integration` | API, Deployment и rollback во временном CI-кластере |
| `staging-and-iris-evidence` | Deployment и внешние проверки постоянного staging и Iris |
| `production-promotion-and-rollback` | `/meta`, promotion, Helm history, отказ кандидата и восстановление |
| `registry-credential-evidence` | Несекретный отчёт credential store и cleanup в CI |

Полные доказательства остаются в artifacts конкретного запуска. В репозитории публикуются только [краткие результаты](validation.md) без credentials и истории настройки доступа.
