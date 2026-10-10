"""Build an offline evidence viewer from captured, inspectable source reports."""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MEDIA = ROOT / "docs/media"
SOURCES = MEDIA / "sources"
PAGES = []


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def source(name, value):
    (SOURCES / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return value


def page(lab, slug, title, subtitle, origin, files, cards, blocks, note, badge="PASS"):
    PAGES.append(dict(lab=lab, slug=slug, title=title, subtitle=subtitle, origin=origin,
                      sources=files, cards=cards, blocks=blocks, note=note, badge=badge))


def code(title, value):
    return {"type": "code", "title": title, "value": value}


def table(title, headers, rows, widths=None):
    return {"type": "table", "title": title, "headers": headers, "rows": rows, "widths": widths}


def http_page(lab, slug, title, subtitle, report, key, note):
    item = report[key]
    response = item["response"]
    if isinstance(response, dict) and "results" in response:
        rendered_response = table("Response body · results", ["№", "Документ / заголовок", "Cosine score"],
                                  [[i+1, result["id"] + " · " + result["title"], result["score"]]
                                   for i,result in enumerate(response["results"])], [8, 70, 22])
    else:
        rendered_response = code("Response body", response)
    page(lab, slug, title, subtitle, "Локальный API · реальный HTTP-ответ", [f"{lab == 'lab1' and 'iris' or 'search'}-http.json"],
         [["HTTP", str(item["status_code"])], ["Метод", item["method"]],
          ["Контракт", "Отклонён" if item["status_code"] == 422 else "Выполнен"]],
         [code(item["method"] + " " + item["endpoint"], item["request"] if item["request"] is not None else "Без тела запроса"),
          rendered_response], note,
         "EXPECTED 422" if item["status_code"] == 422 else "HTTP 200")


def deployment(item):
    spec = item["spec"]["template"]["spec"]
    container = spec["containers"][0]
    return {"name": item["metadata"]["name"], "namespace": item["metadata"]["namespace"],
            "replicas": item["spec"]["replicas"],
            "ready_replicas": item["status"].get("readyReplicas", 0),
            "available_replicas": item["status"].get("availableReplicas", 0),
            "image": container["image"], "resources": container["resources"],
            "pod_security": spec.get("securityContext", {}),
            "container_security": container.get("securityContext", {}),
            "automount_service_account_token": spec.get("automountServiceAccountToken"),
            "probes": {key: container[key] for key in ("startupProbe", "readinessProbe", "livenessProbe") if key in container}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--teaching-artifacts", type=Path, required=True,
                        help="Previously downloaded artifacts of the successful teaching deployment")
    parser.add_argument("--deployments", type=Path, required=True,
                        help="Saved kubectl get of the three owned Deployments")
    args = parser.parse_args()
    raw = args.teaching_artifacts
    own = {item["metadata"]["name"]: deployment(item) for item in read(args.deployments)["items"]
           if item["metadata"]["name"] in ("esolovev-iris", "esolovev-search-staging-mlops-search", "esolovev-search-prod-mlops-search")}
    source("teaching-deployments.json", {"workflow_run": 37905104404, "deployments": list(own.values())})
    prod = raw / "production-promotion-and-rollback"
    promotion = source("teaching-promotion.json", read(prod / "promotion.json"))
    rollback_dir = prod / "esolovev-search-prod/reverse"
    restored = read(rollback_dir / "restored/meta.json")
    before = read(rollback_dir / "previous/meta.json")
    reverse = read(rollback_dir / "candidate/smoke.json")
    rollback = source("teaching-rollback.json", {
        "workflow_run": 37905104404, "rollback": read(rollback_dir / "rollback.json"),
        "candidate_failure": read(rollback_dir / "candidate/failure.json"),
        "candidate_readiness": reverse["ready"], "previous_meta": before, "restored_meta": restored,
        "quality_before": read(rollback_dir / "previous/quality.json"),
        "quality_candidate": read(rollback_dir / "candidate/quality.json"),
        "quality_restored": read(rollback_dir / "restored/quality.json"),
        "history": [{k: item[k] for k in ("revision", "status", "rollback_revision") if k in item}
                    for item in read(rollback_dir / "history-after.json")]})
    iris_report = read(ROOT / "docs/verification/lab1.json")
    registry = source("iris-registry.json", iris_report["registry"])
    ci = read(SOURCES / "teaching-pipeline.json")
    if ci["conclusion"] != "success" or any(job["conclusion"] != "success" for job in ci["jobs"]):
        raise RuntimeError("Teaching pipeline is not fully successful")
    origin = "Учебный Kubernetes · Actions run #37905104404 · сохранённая проверка"
    iris = read(SOURCES / "iris-http.json")
    model = read(SOURCES / "iris-model.json")
    page("lab1", "model", "Обученный классификатор", "Данные, параметры и артефакт модели", "Локальная сборка · train.py", ["iris-model.json", "iris-training.json"],
         [["Объекты Iris", str(model["samples"])], ["Деревья", str(model["n_estimators"])], ["Классы", "3"]],
         [table("Контракт признаков", ["№", "Признак"], [[str(i+1), f] for i,f in enumerate(model["features"])]),
          code("model.joblib", {k: model[k] for k in ("estimator", "random_state", "classes", "artifact_sha256", "artifact_bytes")})],
         "SHA-256 идентифицирует этот локальный артефакт; модель доставляется вместе с приложением.")
    http_page("lab1", "health", "Readiness после загрузки модели", "GET /health", iris, "health", "Readiness подтверждает загруженную модель; /live проверяет доступность процесса.")
    for class_id, key in enumerate(("setosa", "versicolor", "virginica")):
        http_page("lab1", key, f"Предсказание: {key}", f"POST /predict · class_id={class_id}", iris, key,
                  "Четыре числовых признака поступают в обученный RandomForest. Ответ содержит класс и версию модели.")
    http_page("lab1", "invalid-size", "Неверная размерность", "API отклоняет два признака вместо четырёх", iris, "invalid-size", "Невалидный запрос отклоняется до вызова модели. Ожидаемый HTTP-статус — 422.")
    http_page("lab1", "invalid-type", "Строгая проверка типов", "Bool не принимается как числовой признак", iris, "invalid-type", "Значение true отклонено строгой числовой схемой. Никакого неявного преобразования в 1.")
    for lab, prefix in (("lab1", "iris"), ("lab2", "search")):
        test = read(SOURCES / f"{prefix}-tests.json")
        external = read(SOURCES / f"{prefix}-external-api.json")
        count = int(re.search(r"(\d+) passed", test["stdout"])[1])
        if test["exit_code"] != 0 or external["exit_code"] != 0:
            raise RuntimeError(f"{lab} verification failed")
        page(lab, "tests", "Автоматические проверки", "Unit / API contract / внешняя проверка HTTP", "Локальный запуск · pytest и acceptance scripts",
             [f"{prefix}-tests.json", f"{prefix}-external-api.json"], [["Тесты", str(count)], ["Exit code", str(test["exit_code"])], ["Внешний API", "PASS"]],
             [code(test["command"], test["stdout"]), code(external["command"], external["stdout"])],
             "Тесты выполняются отдельно для каждого приложения; внешняя проверка обращается к настоящему HTTP-сервису.")
        resources = [own["esolovev-iris"]] if lab == "lab1" else [own["esolovev-search-staging-mlops-search"], own["esolovev-search-prod-mlops-search"]]
        page(lab, "kubernetes", "Готовые Deployment", "Развёртывание опубликованных образов по digest", origin, ["teaching-deployments.json"],
             [["Deployment", str(len(resources))], ["Available", ", ".join(f"{r['available_replicas']}/{r['replicas']}" for r in resources)], ["Namespace", "mlops-students"]],
             [table("Состояние ресурсов", ["Deployment", "Ready", "Available"], [[r["name"], r["ready_replicas"], r["available_replicas"]] for r in resources]),
              code("Container image", {r["name"]: r["image"] for r in resources})],
             "Снимок построен по сохранённому kubectl get; он подтверждает состояние проверенного выпуска, а не текущее состояние кластера.")
        resource = resources[-1]
        page(lab, "security", "Ограничения runtime", "Security context, ресурсы и probes в фактическом Deployment", origin, ["teaching-deployments.json"],
             [["UID / GID", "10001"], ["Filesystem", "Read-only"], ["Capabilities", "Drop ALL"]],
             [code("Pod / container security", {"pod": resource["pod_security"], "container": resource["container_security"], "automountServiceAccountToken": resource["automount_service_account_token"]}),
              code("Resources / readiness / liveness", {"resources": resource["resources"], "probes": resource["probes"]})],
             "Контейнер работает без root и повышения привилегий. CPU и память ограничены; startup, readiness и liveness имеют отдельные роли.")
        page(lab, "pipeline", "Полный pipeline", "От тестов до учебного production", "GitHub Actions API · run #37905104404", ["teaching-pipeline.json"],
             [["Workflow", "SUCCESS"], ["Jobs", str(len(ci["jobs"]))], ["Build", ci["build_revision"][:12]]],
             [table("Jobs", ["Этап", "Статус", "Результат"], [[j["name"], j["status"], j["conclusion"]] for j in ci["jobs"]]),
              code("Проверенный выпуск", {"run_id": ci["run_id"], "build_revision": ci["build_revision"], "url": ci["url"]})],
             "Это полный ручной запуск с deploy-staging и promote-production. Успешный push без деплоя подтверждает другой набор этапов.")
    page("lab1", "registry", "Registry credentials через pass", "Проверка docker login и authenticated pull на учебной ВМ", "Сохранённая проверка registry · docs/verification/lab1.json", ["iris-registry.json"],
         [["Login", "SUCCESS"], ["Credential store", "pass"], ["Authenticated pull", "PASS"]],
         [table("Проверки credential helper", ["Проверка", "Результат"], [[k, str(v)] for k,v in registry.items()]),
          code("Опубликованный Iris image", iris_report["image"])],
         "Credentials не встроены в Docker config. Временный registry credential удалён после проверки; секретов в демонстрации нет.")
    search = read(SOURCES / "search-http.json")
    traced = search["search"]
    page("lab2", "request-id", "Трассировка запроса", "X-Request-ID совпадает в заголовке и теле ответа", "Локальный API · реальный HTTP-ответ", ["search-http.json"],
         [["Request ID", traced["headers"]["x-request-id"]], ["HTTP", str(traced["status_code"])], ["Index version", traced["response"]["index_version"]]],
         [code("HTTP response headers", traced["headers"]),
          code("Response identity", {k: traced["response"][k] for k in ("request_id", "query", "index_version", "took_ms")})],
         "Корреляционный идентификатор передан клиентом. Сервис возвращает его и записывает в структурированный access log.")
    for slug, title, sub, key, note in (
        ("ready", "Готовность индекса", "GET /readyz", "ready", "API принимает трафик после проверки и загрузки индекса. Ответ содержит версию индекса и размер корпуса."),
        ("search", "Поиск по базе знаний", "POST /v1/search · top-3", "search", "Результаты упорядочены по cosine similarity. Запрос про возврат модели находит doc-rollback первым."),
        ("recommendations", "Похожие документы", "GET /v1/documents/doc-rollback/recommendations", "recommendations", "Рекомендации используют тот же индекс. Исходный документ исключается из выдачи."),
        ("invalid", "Пустой запрос отклонён", "Строка из пробелов после нормализации не проходит контракт", "invalid", "Проверка длины выполняется после удаления пробелов. Ожидаемый ответ — 422."),
        ("metrics", "Метрики сервиса", "GET /metrics · Prometheus exposition", "metrics", "Счётчики HTTP и search, суммарная latency и gauge загруженного индекса доступны для мониторинга.")):
        http_page("lab2", slug, title, sub, search, key, note)
    build = read(SOURCES / "search-reproducibility.json")
    meta = build["first"]
    page("lab2", "index", "Контракт retrieval-индекса", "Hybrid word/char TF-IDF + cosine similarity", "Локальная сборка · build_index.py", ["search-build.json"],
         [["Документы", str(meta["documents"])], ["Признаки", str(meta["features"])], ["Index version", meta["index_version"]]],
         [code("Metadata / fingerprint", meta)], "Metadata связывает индекс с корпусом, параметрами и версиями библиотек. SHA-256 проверяется при загрузке.")
    page("lab2", "reproducibility", "Повторная сборка совпадает", "Два отдельных запуска build_index.py", "Локальная сборка · сравнение metadata и SHA-256", ["search-reproducibility.json", "search-rebuild.json"],
         [["Metadata", "IDENTICAL"], ["SHA-256", "IDENTICAL"], ["Index version", meta["index_version"]]],
         [table("Сравнение сборок", ["Поле", "Build A", "Build B"], [[k, build["first"][k], build["second"][k]] for k in ("index_version", "documents", "features")]),
          code("Artifact checksum", {"first": build["first"]["artifact_sha256"], "second": build["second"]["artifact_sha256"], "metadata_equal": build["metadata_equal"], "sha256_equal": build["sha256_equal"]})],
         "Сравниваются реальные файлы, полученные в разных процессах. Проверка не подменяет checksum заранее заданным значением.")
    for mode in ("normal", "reverse"):
        quality = read(SOURCES / f"search-quality-{mode}.json")
        page("lab2", f"quality-{mode}", "Качество поиска" if mode == "normal" else "Отрицательный контроль: reverse",
             "Восемь независимых контрольных запросов", "Локальная оценка · check_quality.py", [f"search-quality-{mode}.json", "search-quality.json"],
             [["MRR@3", str(quality["mrr"])], ["Hit rate@3", str(quality["hit_rate_at_3"])], ["Macro recall@3", str(quality["macro_recall_at_3"])]],
             [{"type": "quality", "value": quality}, table("Выдача на контрольных запросах", ["Запрос", "Top-3", "Релевантные"],
                [[c["query"], ", ".join(c["top3"]), ", ".join(c["relevant"])] for c in quality["cases"]])],
             "Порог MRR@3 ≥ 0.85, hit rate@3 ≥ 0.90. Macro recall@3 показан отдельно и не подменяет query hit rate.",
             "PASS" if mode == "normal" else "REJECTED AS EXPECTED")
    stage, production = promotion["staging"], promotion["prod"]
    page("lab2", "promotion", "Одна сборка в двух средах", "Staging → production без пересборки", origin, ["teaching-promotion.json"],
         [["Digest", "SAME"], ["Build / index", "SAME"], ["Ranking", "normal"]],
         [table("Идентичность релиза", ["Поле", "Staging", "Production"], [[k, stage["meta"][k], production["meta"][k]] for k in ("environment", "build_revision", "index_version", "ranking_mode")]),
          code("Image / artifact fingerprint", {"staging": stage["image"], "production": production["image"], "artifact_sha256": stage["meta"]["artifact_sha256"]})],
         "Сравнение включает реальный Deployment image и /meta обоих окружений, включая SHA-256 артефакта.")
    page("lab2", "rollback", "Откат восстановил рабочий релиз", "Healthy API → провал quality gate → Helm rollback", origin, ["teaching-rollback.json"],
         [["Readiness кандидата", rollback["candidate_readiness"]["status"]], ["MRR кандидата", str(rollback["quality_candidate"]["mrr"])], ["MRR после rollback", str(rollback["quality_restored"]["mrr"])]],
         [table("Проверяемый сценарий", ["Этап", "Ranking", "MRR@3", "Результат"],
                [["Предыдущая версия", before["ranking_mode"], rollback["quality_before"]["mrr"], "PASS"],
                 ["Плохой кандидат", "reverse", rollback["quality_candidate"]["mrr"], "semantic_quality"],
                 ["Восстановленная версия", restored["ranking_mode"], rollback["quality_restored"]["mrr"], "PASS"]]),
          code("Rollback verification", rollback["rollback"])],
         "Readiness плохого кандидата была ready. Semantic smoke поймал деградацию и подтвердил возврат к прежним digest, build и index.")
    source("pages.json", PAGES)
    template = (Path(__file__).with_name("viewer.html")).read_text(encoding="utf-8")
    # Escape closing script sequences if future corpora contain HTML-like text.
    data = json.dumps(PAGES, ensure_ascii=False).replace("</", "<\\/")
    (MEDIA / "index.html").write_text(template.replace("__PAGES__", data), encoding="utf-8")
    print(json.dumps({"pages": len(PAGES), "labs": {lab: sum(p["lab"] == lab for p in PAGES) for lab in ("lab1", "lab2")}}))


if __name__ == "__main__":
    main()
