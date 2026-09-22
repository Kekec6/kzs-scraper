# KZS scraper – prestopi / ekipe / HTML pregled

Lokalni scrape → `output/html/` → GitHub Pages.

## Lokalno

```bash
pip install -r requirements.txt
python kzs_new_player.py
# HTML: output/html/index.html
```

Po scrapu:

```bash
git add data/ output/html/
git commit -m "update scrape"
git push
```

GitHub Action **Deploy Pages** objavi `output/html` na Pages.

## GitHub Pages

1. Repo **Settings → Pages → Source: GitHub Actions**
2. Po pushu na `main` (ali ročno: Actions → Deploy Pages) je stran na:

`https://<uporabnik>.github.io/<repo>/`

3. V `config.py` nastavi:

```python
'html_public_base': 'https://<uporabnik>.github.io/<repo>',
```

**Opomba:** Pages URL je **javen**, če je repo javen. Za zasebno rabiš private repo + plan, ki dovoli private Pages, ali geslo na drugem hostu.

## Actions

| Workflow | Kdaj |
|---|---|
| **Deploy Pages** | push `output/html/**` ali ročno |
| **Scrape and publish** | ročno (Selenium na Ubuntu) → commit → sproži Pages |

Priporočilo: scrape na svojem Macu (zanesljiveje), Action samo za deploy.
