# Учебный Kubernetes

[Каталог](../README.md) · [CI/CD](delivery.md) · [Knowledge Portal](../lab3/README.md)

| Параметр | Профиль |
|---|---|
| Namespace | itmo-student-01 |
| API | https://37.18.117.109:6443 |
| Kubernetes | v1.36.4 |
| CPU quota requests / limits | 2600m / 2600m |
| Memory quota requests / limits | 4G / 4G: 4 000 000 000 байт |
| NodePort / LoadBalancer | Запрещены |
| HTTP Gateway | envoy-gateway-system/itmo-shared, listener http-student-01 |
| Gateway address | 37.18.117.114, порт 80 |
| Hostname | `<app>.itmo-student-01.37.18.117.114.sslip.io` |

Конфигурация TLS использует выданный CA. Передавайте kubeconfig явно или через окружение конкретного процесса. Файл и токен не входят в Git, образы и отчёты. Actions восстанавливает конфигурацию из KUBE_CONFIG_B64 во временный файл.

Одинаковые суммарные quota requests/limits не требуют равенства ресурсов каждого контейнера. Admission допускает разные requests и limits. В сумме должны выполняться оба ограничения. 4G и 4Gi имеют разный размер; при планировании применяется фактическое 4G.

Storage/PVC не ограничены ключами namespace ResourceQuota. Это не подтверждает неограниченную физическую ёмкость. Доступны cloudru-hdd, cloudru-ssd, cloudru-nvme с WaitForFirstConsumer, расширением и reclaimPolicy Delete. PostgreSQL для небольшого SQLite-корпуса не требуется.

## Профили приложений

| Профиль | CPU limits | Memory limits |
|---|---|---|
| Iris + Search staging + Search production | 600m | 2048Mi |
| Knowledge Portal: Ollama + MCP + portal | 2200m | 3584Mi |

Первые две работы помещаются одновременно. Третий профиль запускается отдельно: все три с полными лимитами превышают квоту памяти. Переключение описано в [RUNBOOK](../lab3/RUNBOOK.md#kubernetes). Общая квота и чужие ресурсы не изменяются.

## Маршруты первых двух работ

- Iris: iris.itmo-student-01.37.18.117.114.sslip.io.
- Search staging: search-staging.itmo-student-01.37.18.117.114.sslip.io.
- Search production: search.itmo-student-01.37.18.117.114.sslip.io.

Workflow создаёт HTTPRoute после проверки Deployment и ждёт Accepted/ResolvedRefs. Наличие hostname не означает доступность приложения. Фактическое состояние и конкретный pipeline приведены в [результатах](validation.md).

MCP, Ollama и портал закрытой базы имеют только ClusterIP. Для проверки используется localhost port-forward; открытый HTTP Gateway не подходит для передачи секретов и закрытых документов.
