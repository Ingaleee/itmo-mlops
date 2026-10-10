"""Generate the lab galleries from the evidence viewer's page catalog."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
pages = json.loads((ROOT / "docs/media/sources/pages.json").read_text(encoding="utf-8"))
walkthroughs = {
    "lab1": [("api-demo", "API: readiness, три класса и валидация"),
             ("delivery-demo", "Доставка: обучение, тесты, CI, Kubernetes и registry")],
    "lab2": [("retrieval-demo", "Retrieval: индекс, поиск, рекомендации и метрики"),
             ("release-demo", "Выпуск: quality gate, promotion и rollback")],
}
for lab, title in (("lab1", "Iris Classifier"), ("lab2", "Runbook Search")):
    local = [p for p in pages if p["lab"] == lab]
    text = [f"# {title} — демонстрация", "", "[Описание проекта](README.md) · [Каталог лабораторных](../README.md) · [Результаты проверок](../docs/validation.md)", "",
            f"**{len(local)+2} скриншотов и два видеообзора** показывают отдельные свойства реализации. Каждый снимок сопровождается исходными данными; снимок общего pipeline используется в обеих галереях.", "",
            "API, тесты и сборка индекса записаны при локальном выполнении. Состояние учебного Kubernetes, promotion и rollback взяты из артефактов [успешного pipeline](https://github.com/Ingaleee/itmo-mlops/actions/runs/37905104404). Эти сохранённые результаты не являются мониторингом текущего состояния стенда.", "",
            "Скриншоты сняты в браузере: интерфейсы OpenAPI и GitHub показаны напрямую, остальные результаты — в [просмотрщике](../docs/media/index.html). Видео составлены из последовательности экранов просмотрщика; анимация в Markdown служит предпросмотром MP4. Все отображаемые ответы и метрики получены из реальных запусков.", "", "## Видео", ""]
    for slug, caption in walkthroughs[lab]:
        text += [f"### {caption}", "", f"[![{caption}](../docs/media/{lab}/{slug}.gif)](../docs/media/{lab}/{slug}.mp4)", "",
                 f"[Скачать MP4](../docs/media/{lab}/{slug}.mp4) · 30 секунд · без звука", ""]
    text += ["## Скриншоты", "", "Изображения открываются в полном разрешении. JSON-источники содержат запросы, ответы, вывод команд или сохранённые параметры выпуска.", ""]
    prefix = "iris" if lab == "lab1" else "search"
    text += ["### OpenAPI — интерфейс работающего сервиса", "", f"![OpenAPI {title}](../docs/media/{lab}/openapi.jpg)", "",
             f"Настоящий Swagger UI локального сервиса. [Сохранённая схема API](../docs/media/sources/{prefix}-openapi.json) описывает endpoints и ограничения запросов.", "",
             "### GitHub Actions — успешный полный workflow", "", "![Полный успешный workflow](../docs/media/shared/github-actions.jpg)", "",
             "Все пять jobs завершены, включая deploy-staging и promote-production. [Открыть запуск](https://github.com/Ingaleee/itmo-mlops/actions/runs/37905104404) · [Данные GitHub API](../docs/media/sources/teaching-pipeline.json).", ""]
    for i, p in enumerate(local, 1):
        text += [f"### {i}. {p['title']}", "", f"![{p['title']}](../docs/media/{lab}/{p['slug']}.jpg)", "", p["note"], "",
                 "Источник: " + " · ".join(f"[{name}](../docs/media/sources/{name})" for name in p["sources"]) + ".", ""]
    text += ["## Происхождение файлов", "", "[Манифест](../docs/media/manifest.json) перечисляет изображения и видео, их размеры, SHA-256 и источники. Порядок воспроизведения и обновления материалов описан в [инструкции](../docs/media/README.md).", ""]
    (ROOT / lab / "DEMO.md").write_text("\n".join(text), encoding="utf-8")
print("Lab galleries written")
