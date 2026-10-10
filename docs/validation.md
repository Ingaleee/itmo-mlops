# Проверки и результаты

[Каталог проектов](../README.md) · [CI/CD](delivery.md)

Результаты привязаны к build revision и digest проверенного релиза. Новая сборка получает собственные идентификаторы и CI artifacts.

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
