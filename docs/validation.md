# Проверки и результаты

[Каталог проектов](../README.md) · [CI/CD](delivery.md)

Результаты привязаны к build revision и digest проверенного релиза. Новая сборка получает собственные идентификаторы и CI artifacts.

Визуальные подтверждения: [Iris](../lab1/DEMO.md), [Search](../lab2/DEMO.md) и [Knowledge Portal](../lab3/DEMO.md). Галереи связывают скриншоты и видео с JSON-источниками; [манифест медиа](media/manifest.json) содержит SHA-256 файлов.

## Персональный учебный кластер

[Запуск 43422084305](https://github.com/Ingaleee/itmo-mlops/actions/runs/43422084305), revision `789b2b1`: тесты, сборка и интеграция опубликованных образов в Kubernetes внутри CI прошли. Staging на `itmo-student-01` остановился до API-проверок: узел получает ImagePullBackOff, TLS handshake timeout и периодические ошибки DNS при скачивании образа.

При повторной попытке Iris прошёл внешнюю API-проверку, однако Search staging снова остановился на скачивании образа с DNS/TLS-ошибкой. Дополнительные credentials не требуются: анонимный pull этих образов подтверждён. Production и rollback на новом стенде не выполнялись. Следующие таблицы описывают сохранённый успешный релиз предыдущего стенда, а не доступность нового.

## Knowledge Portal

Проверки контрактов, приватности, отказов, настоящего MCP-процесса и отмены HTTP через TCP: 62 passed. На исходном корпусе независимый MCP-клиент подтвердил три tools, точные редакции и top-5 источников для К01–К08. Локальный privacy audit подтвердил происхождение всех восьми открытых контекстов и исключение закрытой цитаты, без внешних запросов.

Настоящие генерации llm7.io и Ollama CPU выполнены через портал. Итоговый локальный CPU-прогон прошёл все 8 вопросов: latency 25,9–53,6 с, максимальный промпт 972 токена. [Машинный отчёт](verification/lab3-local.json) и [ответы с источниками](media/sources/knowledge-local-controls.json) сохраняют результаты. Облачная Nemo отвечала неполно на части сложных вопросов; этот прогон не считается прошедшим все 8 проверок. Синтетический mock не считается настоящим провайдером.

[Скриншоты и видео портала](../lab3/DEMO.md) получены при реальном локальном запуске. В отдельном Linux Kubernetes на исходном корпусе прошли все восемь CPU-ответов: 36,6–68,8 с, контекст 2048 токенов, пик cgroup-памяти 2,89 ГиБ, OOM отсутствует. После пересоздания Pod SHA-256 весов сохранился, К01 снова прошёл за 46,3 с. [Отчёт ресурсов и перезапуска](verification/lab3-kubernetes-local.json) и [ответы с источниками](media/sources/knowledge-kubernetes-controls.json) относятся к собственному k3d с выделенным томом.

На учебном кластере прошёл server dry-run, создан и подключён PVC 5Gi. Запуск приложений остановился на скачивании GHCR image с TLS handshake timeout. Третий профиль остановлен, прежние replicas Iris и Search восстановлены. [Состояние поставки](verification/current-delivery.json) и [снимок ресурсов](verification/teaching-workloads.json) отделяют эту незавершённую поставку от успешных изолированных проверок.

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

Для Iris и Search прошли **49 тестов**, без failures и errors. Аудит их закреплённых runtime-зависимостей: **19 пакетов, 0 известных advisory**. Проверки Knowledge Portal приведены отдельно выше. Gitleaks не обнаружил секретов в проверенной Git-истории.

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

## Чистый Kubernetes в CI

[Изолированный CI](https://github.com/Ingaleee/itmo-mlops/actions/runs/43975343298) подтвердил скачивание 2 497 281 120 байт с правильным SHA-256 и регистрацию модели без рестартов init containers. На процессоре runner выбранный AMX backend превысил 3 ГиБ при загрузке. CPU-образ исключает этот вариант; остальные официальные CPU backend выбираются автоматически. Новый предел модели 3200Mi, всего стека 3712Mi, ниже квоты 4G.

[Повторная проверка](https://github.com/Ingaleee/itmo-mlops/actions/runs/43978470485) успешно прошла полный путь на пустом PVC: загрузку, MCP, восемь CPU-ответов (25,3–40,3 с) и генерацию после пересоздания Pod. OOM отсутствует. [Диагностика](verification/lab3-kubernetes-diagnostic.json) связывает исправления с повторной проверкой.

Дополнительный тест обнаружил потерю сигнала HTTP disconnect при опросе через middleware. Backend теперь ожидает ASGI disconnect после чтения тела. Настоящий TCP-тест подтверждает освобождение активного и ожидающего мест; прежняя реализация этот тест проваливает. [CI с проверкой очереди](https://github.com/Ingaleee/itmo-mlops/actions/runs/43979922465) успешно выполнил отмену активного и ожидающего запросов, отказ третьему и следующий К01 с фильтром по подразделу за 36,0 с. На ноутбуке этот дополнительный запрос превысил CPU-бюджет и корректно перешёл в search_only; такой результат не считается прошедшей генерацией. [Итоговый CI](https://github.com/Ingaleee/itmo-mlops/actions/runs/43981776796), revision `2e9c539`, завершился успешно: 62 теста, сборка обоих образов, все восемь CPU-ответов, очередь/отмена, фильтрованный К01 и генерация после пересоздания Pod. [Полный машинный результат](verification/lab3-kubernetes-ci.json) содержит digest, контрольные ответы, cgroup-замеры и проверку PVC.
