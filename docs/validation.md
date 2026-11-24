# Проверки и результаты

[Каталог проектов](../README.md) · [CI/CD](delivery.md) · [Учебный кластер](teaching-cluster.md)

## Iris и Runbook Search

[CI сборки](https://github.com/Ingaleee/itmo-mlops/actions/runs/44912169197) проверяет код, зависимости и опубликованные образы. [Поставка на учебный стенд](https://github.com/Ingaleee/itmo-mlops/actions/runs/44913702769) проверяет Iris, Search staging, production и восстановление после отказа качества в персональном namespace `itmo-student-01`.

| Проверка | Результат |
|---|---|
| Iris | 18 тестов; readiness, три класса и 5 внешних проверок невалидного ввода |
| Search | 37 тестов; API, индекс, оценка качества и корреляция через Gateway |
| Runtime-зависимости | 19 пакетов, 0 известных advisory; OpenTelemetry API 1.45.2 |
| Качество поиска | 8 запросов; MRR@3 = 0.9375, query hit rate@3 = 1.0 |
| Пороги задания | MRR@3 ≥ 0.85, Recall@3 ≥ 0.90 |
| Macro recall@3 | 0.875; отдельная метрика доли найденных релевантных документов |
| Docker Hub | OCI manifests совпадают по SHA-256 с исходными образами, включая SBOM/provenance |
| Deployment | Iris и оба Search доступны; образы закреплены по digest |
| Promotion | Staging и production используют одинаковые image, build revision, index и artifact SHA-256 |
| Reverse-кандидат | Readiness успешен; MRR и query hit rate равны 0; semantic smoke отклоняет релиз |
| Rollback | Восстановлена точная рабочая revision; повторный smoke успешен; история Helm сохранена |
| Финальное состояние | Оба Search используют `normal` и один digest |

`Recall@3` в исходном задании означает долю запросов с релевантным документом в top-3. Macro recall приведён отдельно, чтобы не смешивать определения.

### Доступные API

| Сервис | Интерфейс | Проверяемый ответ |
|---|---|---|
| Iris | [OpenAPI](http://iris.itmo-student-01.mlops.goctf.online/docs) | `/health`, `/predict` |
| Search staging | [OpenAPI](http://search-staging.itmo-student-01.mlops.goctf.online/docs) | `/meta`, `/v1/search` |
| Search production | [OpenAPI](http://search.itmo-student-01.mlops.goctf.online/docs) | `/meta`, `/v1/search` |

Прямой API сохраняет клиентский `X-Request-ID`. Общий Envoy назначает внешний UUID: Gateway-проверка требует его совпадения в заголовке и JSON. Оба пути сохраняют доказательства в `request-ids.json`; настройка общего Gateway не меняется.

Readiness подтверждает загрузку индекса и доступность процесса. Корректность результатов подтверждается отдельными контрольными запросами. Поэтому healthy reverse-кандидат проваливает semantic smoke и вызывает откат.

### Идентификаторы и доказательства

Build revision: `c4605187d09092a527499c8f5147c81b7db31f02`. Поставка использует эту сборку без пересборки.

```text
Iris
docker.io/inga1e/esolovev-iris@sha256:89cfda0d23e193c96b2d2d38338a9896359567f96f81cd71f7267d6582bf9114

Search staging и production
docker.io/inga1e/esolovev-search@sha256:acdae1d4573281058de83eb11c2b98c8e7cc340c13afa2872bf89156732eb5d1

Search index: 1eed508a1515
Artifact SHA-256: 3001846126ae94dd2da4d715f40fe8b178b25cf8eb4dfb2c3e40f5cce05063ed
```

| Отчёт | Что подтверждает |
|---|---|
| [Iris](verification/lab1.json) | HTTP-ответы, образ и credential store |
| [Search](verification/lab2.json) | Качество, promotion, отрицательный контроль и Helm history |
| [Поставка Docker Hub](verification/dockerhub-delivery.json) | Связь сборки, зеркалирования, учебного deployment и отката |
| [Тесты и аудит](verification/ci.json) | 55 тестов и результаты проверки runtime-зависимостей |
| [Ресурсы стенда](verification/teaching-workloads.json) | Снимок собственных Deployment и сохранённого PVC |

Полные artifacts запуска поставки: `dockerhub-staging-and-iris` и `dockerhub-production-and-rollback`. Они содержат `/meta`, Deployment, ответы API, quality reports, отказ кандидата, rollback и Helm history. Исходный CI сохраняет `quality-and-contracts`, `immutable-images` и `local-kubernetes-integration`.

`pass init`, Docker credential helper, login, зашифрованное хранение, authenticated pull и удаление временного credential подтверждены отдельно. В публичные отчёты входят только результаты. Docker Hub credential остаётся в локальном credential store, kubeconfig — в masked Actions secret.

## Knowledge Portal

[CI третьей работы](https://github.com/Ingaleee/itmo-mlops/actions/runs/44960841161), revision `2ffd239ecf0c14a1abd41d843909a2e626f9cdba`, проверяет настоящий MCP-процесс, приватность, отказ и переключение провайдеров, очередь, отмену HTTP-запросов, CPU inference и сохранность модели после пересоздания Pod.

| Проверка | Результат |
|---|---|
| Контракты и интеграция | 64 теста прошли |
| Исходный корпус, локальный CPU | 8/8 контрольных ответов, 25.9–53.6 с |
| Исходный корпус, отдельный Linux Kubernetes | 8/8 ответов, 36.6–68.8 с; OOM отсутствует |
| Чистый Kubernetes в CI | Пустой PVC, загрузка и SHA-256 весов; 8/8 CPU-ответов, 18.2–28.1 с |
| Пересоздание Pod | Новый UID; прежний SHA-256 весов; следующий контрольный ответ успешен |
| Очередь и отмена | Активный и ожидающий запросы отменяются; следующий ответ с фильтром прошёл на настоящей модели |
| Приватность | В CI используется публичный fixture; исходная закрытая карточка и credentials не публикуются |
| Облачный провайдер | Исторический Gemma: 5/8; текущий Codestral не прошёл полноту К06, аккаунт получил quota_exceeded |
| Учебный Kubernetes, исходный корпус | 8/8 CPU-ответов, 43.4–68.0 с; MCP, очередь, отмена и ответ после пересоздания Pod прошли |

[CPU-приёмка на учебном стенде](https://github.com/Ingaleee/itmo-mlops/actions/runs/45368980625) использует опубликованные Docker Hub images без пересборки. [Отчёт](verification/lab3-teaching.json) сохраняет ответы, точные источники, разные UID Pod, совпавший SHA-256 весов и cgroup: OOM и неожиданных перезапусков нет. После проверки третий профиль остановлен; Iris и оба Search восстановлены с прежними Pod templates, их публичные API повторно проверены.

CPU-стек укладывается в лимиты `2200m` и `3712Mi`, ниже фактической квоты `4G`. Он запускается отдельным профилем: совместный запуск всех трёх работ превышает квоту памяти. Ключ llm7 не установлен в учебный кластер, поэтому облачный маршрут там не подтверждён. На загруженном ноутбуке дополнительный фильтрованный запрос может превышать CPU-бюджет и возвращать `search_only`; этот результат не считается успешной генерацией.

Сохранённый облачный прогон через настоящий локальный портал подтверждает пять ответов Gemma, включая числовую сверку К04. В актуальном каталоге Gemma стала paid-only; учебный профиль использует `codestral-latest`, для которого подтверждены JSON mode и `usage_based_only: false`. Его ответ на К06 не прошёл строгую проверку полноты суммы и разницы. Аккаунт затем получил `insufficient_quota / quota_exceeded`; платный тариф не подключён, полный облачный набор не пройден. [Облачный отчёт](verification/lab3-cloud.json) отделяет этот результат от CPU и учебного namespace.

Отдельная [проверка исходящего HTTPS](https://github.com/Ingaleee/itmo-mlops/actions/runs/45373583562) из временного Job не получила ответ от `api.llm7.io` за 5.3 с (`URLError`), при этом `ya.ru` вернул HTTP 200 с проверенным TLS. [Сетевой отчёт](verification/lab3-egress.json) не содержит credentials или тел ответов; Job удалён. Это ограничение учебного окружения проверяется отдельно от качества модели и бюджета аккаунта.

Актуальный [локальный аудит приватности](verification/lab3-privacy.json) подтверждает все восемь контекстов, точные редакции, число токенов текущего промпта и исключение опасной цитаты без внешних запросов. Исторические fingerprints рядом с медиа сохраняются как доказательства соответствующего выпуска.

Отчёты: [локальный CPU](verification/lab3-local.json), [Linux Kubernetes и PVC](verification/lab3-kubernetes-local.json), [полный Kubernetes CI](verification/lab3-kubernetes-ci.json). Команды запуска и переключения профилей — в [RUNBOOK](../lab3/RUNBOOK.md).

## Визуальные материалы

[Iris](../lab1/DEMO.md), [Search](../lab2/DEMO.md) и [Knowledge Portal](../lab3/DEMO.md) содержат реальные снимки и видеообзоры. Источник и проверяемый выпуск указаны в подписях: сохранённый снимок не является мониторингом кластера. [Манифест](media/manifest.json) содержит SHA-256 медиа.

Технические проверки подтверждают указанные ревизии и сценарии. Отметку о приёмке выставляет преподаватель.
