# Запуск Knowledge Portal

[Описание](README.md) · [Ресурсы кластера](../docs/teaching-cluster.md)

## Подготовка

Python 3.12, отдельное окружение, `pip install -r requirements-dev.txt`. Команды выполняются из `lab3`:

```bash
python model/fetch_tokenizer.py
python model/fetch_model.py --directory /private/models
python scripts/inspect_corpus.py /private/corpus.json
python scripts/check_privacy.py /private/corpus.json
```

GGUF требует около 2,5 ГБ свободного места без runtime. Файл сохраняется под content-addressed именем; повторный запуск сверяет SHA-256 и использует существующие веса. Не включайте их в публичный build context. Fingerprints — в [runtime.json](model/runtime.json).

CPU-контейнер переносит бинарный файл и библиотеки из закреплённого официального Ollama, исключая GPU payload и AMX backend. На CPU с AMX этот backend перепаковывает веса и превысил лимит 3 ГиБ в чистом CI. Остальные официальные CPU-варианты сохраняют автоматический выбор инструкций. Веса и корпус доставляются отдельно.

## Локальные сервисы

Создайте два случайных токена не короче 24 символов: MCP и вход в портал. Храните их и ключ llm7 вне Git. Значения задавайте в окружении backend, не вставляя в отчёт или историю команд.

| Переменная | Назначение |
|---|---|
| KB_CORPUS | Исходный корпус при старте MCP |
| KB_DATABASE | SQLite snapshot, default artifacts/knowledge.db |
| MCP_SERVICE_TOKEN | Общий секрет portal → MCP |
| PORTAL_ACCESS_TOKEN | Вход пользователя |
| MCP_URL | Например http://127.0.0.1:18080/mcp |
| LLM7_API_KEY | Бесплатный API token, только backend |
| CLOUD_MODEL | Default mistral-Nemo-Instruct-2407 |
| LOCAL_BASE_URL | Например http://127.0.0.1:11440/v1 |
| LOCAL_MODEL | line-local |
| LOCAL_BUDGET_SECONDS | CPU-вызов вместе с очередью: 105 с, допустимо 15–180 с |

```bash
python -m uvicorn app.mcp_server:create_app --factory --host 127.0.0.1 --port 18080 --no-access-log
python -m uvicorn app.portal:create_app --factory --host 127.0.0.1 --port 18081 --no-access-log
```

Запустите Ollama с одним параллельным слотом, CPU и контекстом 2048. Импортируйте [Modelfile](model/Modelfile), подставив локальное расположение проверенного GGUF вместо `/weights/blobs/...`. Портал: http://127.0.0.1:18081; токен вводится в форме, не в URL.

Для остановки завершайте только процессы лабораторной. Веса и SQLite можно сохранить. Общий Docker Desktop и другие проекты перезапускать не требуется.

## Kubernetes

Профиль — itmo-student-01. Kubeconfig указывается явно; глобальный context не меняется.

| Deployment | CPU requests / limits | Memory requests / limits |
|---|---|---|
| llm-local | 1000m / 1800m | 2560Mi / 3200Mi |
| kb-mcp | 100m / 200m | 128Mi / 256Mi |
| knowledge-portal | 100m / 200m | 128Mi / 256Mi |
| Всего limits | 2200m | 3712Mi = 3 892 314 112 байт |

Сумма ниже quota 2600m / 4G. Полные профили всех лабораторных одновременно не помещаются в память квоты. Перед третьей сохраните доказательства первых работ и уменьшите только их собственные replicas до 0; Helm history сохраняется. После демонстрации остановите третий профиль и восстановите прежние replicas. Namespace, квота и чужие ресурсы не удаляются.

1. Получите knowledge-images.json из workflow **Knowledge Portal**. Адреса должны содержать digest.
2. Установите корпус и credentials напрямую с локального компьютера:

```bash
python scripts/prepare_secrets.py --kubeconfig /private/student.kubeconfig \
  --corpus /private/corpus.json --mcp-token /private/mcp.token \
  --portal-token /private/portal.token --cloud-key /private/llm7.token
```

3. Проверьте admission, затем повторите с `--apply` для установки:

```bash
python scripts/deploy.py --kubeconfig /private/student.kubeconfig \
  --app-image ghcr.io/ingaleee/esolovev-knowledge@sha256:FULL_DIGEST \
  --ollama-image ghcr.io/ingaleee/esolovev-ollama-cpu@sha256:FULL_DIGEST
```

PVC knowledge-models хранит веса и manifest Ollama. Init containers проверяют SHA, регистрируют модель и проверяют её чтение до read-only монтажа в основном контейнере. OLLAMA_NOPRUNE предотвращает удаление ещё не зарегистрированного GGUF при первом старте. MCP получает корпус из Secret и строит индекс. Recreate не требует дополнительного Pod.

Startup probe [предзагружает модель](https://docs.ollama.com/faq#how-can-i-preload-a-model-into-ollama-to-get-faster-response-times) штатной командой Ollama; холодная загрузка завершается до готовности Pod. OLLAMA_KEEP_ALIVE=-1 удерживает единственную модель в выделенном сервисе. LLAMA_ARG_CACHE_RAM=0 отключает RAM-кеш завершённых промптов в llama-server: его стандартный предел 8 ГиБ несовместим с квотой этого профиля. Контекст активного запроса остаётся 2048 токенов. Измерения выполняются на серии разных вопросов, чтобы обнаружить накопление памяти.

4. Откройте портал через localhost:

```bash
kubectl --kubeconfig /private/student.kubeconfig -n itmo-student-01 \
  port-forward --address=127.0.0.1 service/knowledge-portal 18081:8000
```

5. Выполните MCP probe через временный port-forward и E2E каждого настоящего провайдера. Пересоздайте собственный Pod модели, дождитесь readiness и повторите генерацию. Снимите ресурсы в idle и под нагрузкой. Одних probes недостаточно.

`python scripts/verify_runtime.py --portal-token-file /private/portal.token --output evidence/runtime.json` проверяет настоящую CPU-очередь: одно активное место, одно ожидающее, отказ третьему запросу, отмену обоих и следующий ответ на К01 с фильтром по подразделу. Для него требуется уже готовая модель; облачные запросы не выполняются.

Публичный HTTP Gateway для закрытой базы не создаётся. Для внешней публикации нужен TLS-профиль и проверка доступа.

## Диагностика

| Симптом | Действие |
|---|---|
| ImagePullBackOff | Events собственного Pod: DNS, TLS, registry, digest; токен приложения не исправляет сеть узла |
| MCP 401 / 403 | Сервисные токены и допустимый Origin; Authorization не выводить |
| Tool error | Проверить ID и точную version, не подменять текущей |
| search_only | reason и request_id, контекст, модель, очередь и provider errors |
| Rate limit | Одна попытка, пауза Retry-After, затем одна проба |
| Медленный CPU | Фактические RAM, CPU, prompt tokens и latency |

Fault-provider `testing/cloud_mock.py` запускается только изолированно с mock-key-not-secret. Настоящий API token ему не передаётся. Синтетическая quota не объявляется реальной ошибкой llm7 без подтверждённого provider code.
