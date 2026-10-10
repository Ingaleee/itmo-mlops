# Проверка лабораторных 1 и 2 — 10 октября 2026

Соловьёв Егор Юрьевич, М4206, префикс `esolovev`.

Технические пункты обеих лабораторных проверены. Приёмку и оценку подтверждает преподаватель.

## Учебная ВМ и первая лабораторная

- Доступ по исходному SSH-ключу восстановлен; вход под `esolovev` успешен, срок действия учётной записи не ограничен. По уточнению администратора пароль не требуется: доступ только по ключу.
- Пользователь находится в группе `docker`; Docker, GPG, pass, credential helper, uv, kubectl, Helm и Git доступны.
- В домашней папке ВМ выполнен `pass init`. Docker использует `credsStore=pass`.
- Настоящий `docker login ghcr.io` успешен. Проверены расшифровка credential helper, совпадение credential и отсутствие embedded auth в Docker config.
- Iris скачан на ВМ с проверкой точного digest. Временный токен имел только `packages:read`; после проверки выполнен logout, запись ghcr.io удалена из pass. Приватные ключи не экспортировались.
- Свежая внешняя проверка учебного Iris через port-forward: `/live` и `/health` корректны, предсказания setosa/versicolor/virginica — `0/1/2`, все пять ошибочных входов возвращают 422.

Учебный образ: `ghcr.io/ingaleee/esolovev-iris@sha256:bb255540fbd96a75acd40bd0f6c206c114591da75397f74b2359ce4b4b508e6b`.

## Вторая лабораторная

- Собственные staging и production Deployment имеют READY/available `1/1`.
- В обоих окружениях выполнена свежая проверка восьми контрольных запросов, recommendations, request ID, ошибочного ввода и метрик.
- MRR@3 = **0.9375**, предусмотренный заданием Recall@3 / query hit rate = **1.0**. Дополнительно macro recall@3 = **0.875**.
- Staging и production имеют одинаковые image digest, build revision, index version и SHA-256 model artifact; ranking mode — `normal`.
- История production сохранена: revision 1 normal, 2 reverse, 3 `Rollback to 1`, 4 normal/deployed. Предыдущий полный pipeline сохранил провал reverse по качеству, настоящий Helm rollback и успешную повторную проверку. При текущей проверке релизы не обновлялись.

Учебный образ: `ghcr.io/ingaleee/esolovev-search@sha256:d6513bd56732c4c17fc68cb00fdc58c5a6ca31069cf1752135572fee13b1ec75`.

Build revision: `2a820a01c2148d75e9fbcbc420dd64f2ec114ccc`; index version: `1eed508a1515`; artifact SHA-256: `3001846126ae94dd2da4d715f40fe8b178b25cf8eb4dfb2c3e40f5cce05063ed`.

## CI и доказательства

- [Полный pipeline на учебном Kubernetes](https://github.com/Ingaleee/itmo-mlops/actions/runs/37905104404): все пять jobs успешны, включая deployment, production approval и rollback.
- [CI дополнения от 10 октября](https://github.com/Ingaleee/itmo-mlops/actions/runs/38043253544): test-quality, build-images и local-integration успешны. В скачанном и проверенном по SHA-256 artifact подтверждены 49 тестов (18 Iris + 31 Search), без failures/errors; аудит 19 runtime-пакетов не нашёл известных advisory. Этот push обновил ручной вспомогательный workflow, поэтому учебные deployment jobs пропущены по условию. Работающие учебные релизы подтверждены отдельной свежей проверкой выше.
- [Дополнительная CI-проверка pass/login](https://github.com/Ingaleee/itmo-mlops/actions/runs/37910535663) подтверждает тот же сценарий в отдельной Ubuntu-среде; она учитывается отдельно от выполненной настройки исходной ВМ.
- Gitleaks проверил опубликованную историю после добавления ручного workflow: утечек не найдено.
- [Временный registry access](https://github.com/Ingaleee/itmo-mlops/actions/runs/38043516699) завершился успешно. После использования зашифрованный credential artifact удалён; в отчётах нет токенов или приватных ключей.

Несекретные отчёты: [настройка registry на ВМ](evidence/teaching-vm-registry-2026-10-10.json), [текущие API и Helm history](evidence/teaching-live-2026-10-10.json), [CI-тесты и аудит](evidence/ci-quality-2026-10-10.json).

На локальном компьютере также сохранены Deployment JSON и полные логи проверок. В GitHub artifacts полного учебного pipeline находятся исходные отчёты качества и rollback.
