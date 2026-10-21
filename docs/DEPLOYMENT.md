# Deployment guide · Guide de déploiement

> **EN** — Step-by-step procedure to publish the DI4A website on GitHub Pages.
> **FR** — Procédure pas à pas pour publier le site DI4A sur GitHub Pages. La version française suit la version anglaise.

---

## English

### 0. Prerequisites

- A GitHub account with rights on the organisation that will host the repository (for example `datainnov4africa-web`).
- Git ≥ 2.30 and Python ≥ 3.10 installed locally (`python --version`).
- The repository folder: `C:\AfDB\Momar2\DI4A-Website`.

### 1. Check the build locally

```bash
cd C:\AfDB\Momar2\DI4A-Website
pip install pyyaml
python -m unittest discover -s tests          # unit tests
python scripts/build_site.py --serve          # build dist/ and serve on http://localhost:8080
```

Open <http://localhost:8080/> and check the home page, a theme page, the PDF preview and the language switch. Stop the server with `Ctrl+C`.

### 2. Create the GitHub repository

1. On GitHub, create an **empty public** repository named `DI4A-Website` (no README, no licence, no `.gitignore`).
2. Make sure `repo:` in `site.config.yml` matches `owner/name` (it is only a fallback: the workflow always uses the real repository name).

### 3. First push

```bash
cd C:\AfDB\Momar2\DI4A-Website
git add .
git status            # verify that .env is NOT listed (it is ignored by .gitignore)
git commit -m "feat: DI4A website, catalogue builder and deploy workflow"
git remote add origin https://github.com/<owner>/DI4A-Website.git
git push -u origin main
```

> If you use several GitHub accounts on the same machine, push with an explicit account, e.g. `git remote set-url origin https://<owner>@github.com/<owner>/DI4A-Website.git`, and let the credential manager prompt for that account.

### 4. Let the workflow create the `gh-pages` branch

The push triggers **Actions → Build & deploy site**. Wait for the green check (about one minute). The workflow:

- runs the tests and the build;
- publishes `dist/` to the `gh-pages` branch;
- refreshes the catalogue tables of `README.md` on `main`.

### 5. Enable GitHub Pages (one time)

1. Repository **Settings → Pages**.
2. **Source**: *Deploy from a branch*.
3. **Branch**: `gh-pages`, folder `/ (root)`. Save.
4. After a minute the site is live at `https://<owner>.github.io/DI4A-Website/`.

### 6. Day-to-day: add or remove content

| You do… | Then… | The site… |
|---|---|---|
| Create `content/<New-Theme>/` with `.ipynb` / `.pdf` files | `git add . && git commit -m "content: new theme" && git push` | shows the new theme |
| Delete a folder or a file | commit and push | removes it |
| Edit `_meta.yml` | commit and push | updates titles and descriptions |

Nothing else is required. Files that are not `.ipynb` or `.pdf` are ignored by the site (they may stay in the repository).

### 7. Optional: custom domain

Add a `CNAME` file in `site/` containing the domain, configure the DNS as explained in GitHub's documentation, then set the domain in **Settings → Pages**.

### 8. Troubleshooting

- **Workflow fails on "forbidden token"**: a `download:` value in `_meta.yml` contains an event, place or year. Fix the value; the list of forbidden words is in `site.config.yml`.
- **Colab link opens a 404**: the `gh-pages` branch has not been published yet, or the repository is private. Colab needs a public repository.
- **README not updated**: the workflow needs `permissions: contents: write` (already set) and the "Allow GitHub Actions to create and approve pull requests" option is *not* required.

---

## Français

### 0. Prérequis

- Un compte GitHub avec des droits sur l'organisation qui hébergera le dépôt (par exemple `datainnov4africa-web`).
- Git ≥ 2.30 et Python ≥ 3.10 installés en local (`python --version`).
- Le dossier du dépôt : `C:\AfDB\Momar2\DI4A-Website`.

### 1. Vérifier la construction en local

```bash
cd C:\AfDB\Momar2\DI4A-Website
pip install pyyaml
python -m unittest discover -s tests          # tests unitaires
python scripts/build_site.py --serve          # construit dist/ et sert http://localhost:8080
```

Ouvrez <http://localhost:8080/> et vérifiez l'accueil, une page thème, l'aperçu PDF et le sélecteur de langue. Arrêtez le serveur avec `Ctrl+C`.

### 2. Créer le dépôt GitHub

1. Sur GitHub, créez un dépôt **public et vide** nommé `DI4A-Website` (sans README, licence ni `.gitignore`).
2. Vérifiez que `repo:` dans `site.config.yml` correspond à `propriétaire/nom` (simple valeur de repli : le workflow utilise toujours le nom réel du dépôt).

### 3. Premier envoi

```bash
cd C:\AfDB\Momar2\DI4A-Website
git add .
git status            # vérifiez que .env n'apparaît PAS (il est ignoré par .gitignore)
git commit -m "feat: site DI4A, générateur de catalogue et workflow de déploiement"
git remote add origin https://github.com/<proprietaire>/DI4A-Website.git
git push -u origin main
```

> Si plusieurs comptes GitHub cohabitent sur la machine, poussez avec un compte explicite : `git remote set-url origin https://<proprietaire>@github.com/<proprietaire>/DI4A-Website.git`, puis laissez le gestionnaire d'identifiants demander ce compte.

### 4. Laisser le workflow créer la branche `gh-pages`

Le push déclenche **Actions → Build & deploy site**. Attendez la coche verte (environ une minute). Le workflow :

- exécute les tests et la construction ;
- publie `dist/` sur la branche `gh-pages` ;
- rafraîchit les tableaux du catalogue dans `README.md` sur `main`.

### 5. Activer GitHub Pages (une seule fois)

1. **Settings → Pages** du dépôt.
2. **Source** : *Deploy from a branch*.
3. **Branch** : `gh-pages`, dossier `/ (root)`. Enregistrez.
4. Une minute plus tard, le site est en ligne : `https://<proprietaire>.github.io/DI4A-Website/`.

### 6. Au quotidien : ajouter ou retirer du contenu

| Vous… | Puis… | Le site… |
|---|---|---|
| Créez `content/<Nouveau-Theme>/` avec des fichiers `.ipynb` / `.pdf` | `git add . && git commit -m "content: nouveau thème" && git push` | affiche le nouveau thème |
| Supprimez un dossier ou un fichier | commit et push | le retire |
| Modifiez `_meta.yml` | commit et push | met à jour titres et descriptions |

Rien d'autre n'est nécessaire. Les fichiers qui ne sont ni `.ipynb` ni `.pdf` sont ignorés par le site (ils peuvent rester dans le dépôt).

### 7. Facultatif : nom de domaine personnalisé

Ajoutez un fichier `CNAME` dans `site/` contenant le domaine, configurez le DNS selon la documentation GitHub, puis renseignez le domaine dans **Settings → Pages**.

### 8. Dépannage

- **Le workflow échoue sur « forbidden token »** : une valeur `download:` de `_meta.yml` contient un événement, un lieu ou une année. Corrigez la valeur ; la liste des mots interdits est dans `site.config.yml`.
- **Le lien Colab renvoie une 404** : la branche `gh-pages` n'est pas encore publiée, ou le dépôt est privé. Colab exige un dépôt public.
- **README non mis à jour** : le workflow a besoin de `permissions: contents: write` (déjà présent).
