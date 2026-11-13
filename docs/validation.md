# Проверки и результаты

[Каталог проектов](../README.md) · [CI/CD](delivery.md)

Результаты привязаны к build revision и digest проверенного релиза. Новая сборка получает собственные идентификаторы и CI artifacts.

Визуальные подтверждения: [Iris](../lab1/DEMO.md) и [Search](../lab2/DEMO.md). Галереи связывают скриншоты и видео с JSON-источниками; [манифест медиа](media/manifest.json) содержит SHA-256 файлов.

## Персональный учебный кластер

[Запуск 43422084305](https://github.com/Ingaleee/itmo-mlops/actions/runs/43422084305), revision `789b2b1`: тесты, сборка и интеграция опубликованных образов в Kubernetes внутри CI прошли. Staging на `itmo-student-01` остановился до API-проверок: узел получает ImagePullBackOff, TLS handshake timeout и периодические ошибки DNS при скачивании образа.

Та же проблема подтверждена на отдельном публичном образе Docker Hub и при загрузке неизменяемого Iris digest через зеркало. Диагностический Pod удалён. Production и rollback на новом стенде в этом запуске не выполнялись. Следующие таблицы описывают сохранённый успешный релиз предыдущего стенда, а не доступность нового.

## Knowledge Portal

Синтетические проверки контрактов, приватности, отказов и настоящего MCP-процесса: 53 passed. На исходном корпусе независимый MCP-клиент подтвердил три tools, точные редакции и top-5 источников для К01–К08. Локальный privacy audit подтвердил происхождение всех восьми открытых контекстов и исключение закрытой цитаты, без внешних запросов.

Настоящие генерации llm7.io и Ollama CPU выполнены через портал. Строгий контроль полноты числовых ответов выявил различия между провайдерами; результаты окончательных прогонов фиксируются отдельно. Синтетический mock не считается настоящим провайдером.

Kubernetes-манифесты третьей работы и CPU images реализованы. Запуск модели в Kubernetes, сохранность весов после Pod restart, измерения в кластере и итоговая кластерная приёмка ещё не подтверждены. Публикация кода или images не закрывает эти пункты.

## Iris Classifier

| Проверка | Результат |
|---|---|
| Тесты | 18 passed |
| `/live`, `/health` | Корректные ответы |
| Предсказания | setosa / versicolor / virginica → 0 / 1 / 2 |
| Некорректные входы | 5 внешних проверок с ответом 422 |
| Kubernetes | Deployment доступен, образ закреплён по digest |
| Credential store | pass init, login, шифрование, pull и cleanup подтверждены |

[Машинный отчёт](verification/lab1.json) · [Воспроизвести проверки](../lab1/README.md#проверки)

## Runbook Search

| Проверка | Результат |
|---|---|
| Тесты | 31 passed |
| Контрольные запросы | 8 в каждом окружении |
| MRR@3 | 0.9375 при пороге 0.85 |
| Recall@3 / query hit rate | 1.0 при пороге 0.90 |
| Macro recall@3 | 0.875 |
| API-контракт | Search, recommendations, request ID, validation, probes и metrics прошли |
| Promotion | Digest, build revision, index и artifact SHA-256 двух окружений совпадают |
| Reverse-кандидат | Readiness успешен, качество 0 / 0, кандидат отклонён |
| Rollback | Восстановлена рабочая revision; повторная проверка успешна |
| Итоговое состояние | Оба окружения используют `normal` и один digest |

Последовательность production revisions: `normal → reverse → rollback → normal`. История релиза сохранена.

[Машинный отчёт](verification/lab2.json) · [Воспроизвести проверки](../lab2/README.md#проверки)

## CI и безопасность

Всего **49 тестов**, без failures и errors. Аудит закреплённых runtime-зависимостей: **19 пакетов, 0 известных advisory**. Gitleaks не обнаружил секретов в проверенной Git-истории.

Проверки относятся к указанным артефактам и запуску. Актуальные результаты новых сборок доступны в [Actions](https://github.com/Ingaleee/itmo-mlops/actions).

- [Pipeline с развёртыванием и rollback](https://github.com/Ingaleee/itmo-mlops/actions/runs/37905104404).
- [CI: тесты, сборка и интеграция опубликованных образов](https://github.com/Ingaleee/itmo-mlops/actions/runs/38043253544).
- [Машинный отчёт тестов и аудита](verification/ci.json).

Состав полных artifacts описан в [CI/CD](delivery.md#артефакты).

## Идентификаторы релиза

Build revision: `2a820a01c2148d75e9fbcbc420dd64f2ec114ccc`.

```text
Iris image
ghcr.io/ingaleee/esolovev-iris@sha256:bb255540fbd96a75acd40bd0f6c206c114591da75397f74b2359ce4b4b508e6b

Search image
ghcr.io/ingaleee/esolovev-search@sha256:d6513bd56732c4c17fc68cb00fdc58c5a6ca31069cf1752135572fee13b1ec75

Search index
1eed508a1515

Search artifact SHA-256
3001846126ae94dd2da4d715f40fe8b178b25cf8eb4dfb2c3e40f5cce05063ed
```
