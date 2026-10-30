# vsl_node

Пакет кастомных нод для ComfyUI.

## Ноды

- **VSL Prompt Helper** — генерация/перевод промптов через LLM (llama-router, OpenRouter-совместимые шлюзы, NVIDIA NIM и др.): пресеты подключений с кнопками Save/Update/Delete, api_key, model, прокси (http:// и socks5://), режимы Enhance / Translate Only / Skip, целевые модели Krea 2 / Anima / Illustrious / Qwen / MOSS.
- **vsl_Style_Selector** — галерея стилей (414 стилей, категории, избранное, масштаб превью): выводит промпт выбранного стиля, пустой вывод при снятом выделении.
- **VSL Text Concentrate** — концентрация текста.
- **VSL Image Size** — размер изображения.
- **VSL Min/Max Size** — ограничение размеров.
- **VSL Model Loader (Presets)** — пресеты моделей (через `/vsl/model-presets` роуты).
- **VSL Any Reroute** — универсальный reroute.

## Установка

Скопировать каталог в `ComfyUI/custom_nodes/`, перезапустить ComfyUI.

## Локальные настройки (не в репозитории)

Файлы создаются рядом с нодами по шаблонам `*.example`:

- `vsl_router_presets.json` — пресеты подключений LLM (router_url, api_key, model, proxy) — **содержит API-ключи, в git не попадает**;
- `vsl_model_presets.json` — локальные пути/пресеты моделей;
- `vsl_style_favorites.json` — избранные стили галереи.

## Примечания

- `web/previews/` — 414 превью стилей (галерея vsl_Style_Selector).
- `vsl_prompts.json` — системные промпты (11 ключей), читаются при импорте; правка требует рестарта ComfyUI.
