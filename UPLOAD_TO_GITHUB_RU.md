# Загрузка v0.2 в GitHub полностью онлайн

1. Создай пустой repository `swiss-diptera-id-workbench` на GitHub.
2. В repository нажми **Add file → Upload files** и загрузи ZIP v0.2.
3. Открой **Code → Codespaces → Create codespace on main**.
4. В терминале Codespaces выполни, подставив точное имя архива:

```bash
mkdir -p /tmp/diptera-v02
unzip swiss-diptera-id-workbench_v0.2.zip -d /tmp/diptera-v02
rsync -a /tmp/diptera-v02/swiss-diptera-id-workbench/ ./
git add .
git rm swiss-diptera-id-workbench_v0.2.zip
git commit -m "Add Diptera Foundation Corpus pipeline v0.2"
git push
```

После push код будет лежать нормально по папкам, а не одним ZIP-файлом.

Для manifest pilot Codespaces подходит. Полные datasets, миллионы изображений, embeddings и большое GPU training не храни в GitHub repository; используй object/university storage и отдельный GPU runner.
