# Publishing the Repository on GitHub

## 1. Choose the repository name

Suggested name:

```text
dt-freshness-aware-ndn
```

Suggested short description:

```text
Reproducible ns-3/ndnSIM experiments for application-aware Digital Twin freshness and MEC caching.
```

## 2. Review before publishing

Remove anything that should not be public, especially:

- private paths or credentials;
- unpublished manuscript text you do not want in the repository;
- very large raw result folders;
- generated build artifacts.

The supplied `.gitignore` excludes common ns-3 experiment outputs and Python cache files.

## 3. Choose a license

A public GitHub repository without a license is not automatically reusable as open-source software.

Choose a license before release. MIT is simple and permissive for research code, but check institutional, co-author, sponsor, and dependency requirements first.

## 4. Initialize Git locally

From the repository root:

```bash
git init
git branch -M main
git add .
git commit -m "Initial public release of DT freshness-aware NDN experiment"
```

## 5. Create the GitHub repository

Create an empty public repository on GitHub named, for example:

```text
dt-freshness-aware-ndn
```

Do not initialize it with another README if your local repository already contains this README.

Then connect it:

```bash
git remote add origin https://github.com/<YOUR-USERNAME>/dt-freshness-aware-ndn.git
git push -u origin main
```

If you use the GitHub CLI, the equivalent workflow is:

```bash
gh repo create dt-freshness-aware-ndn \
  --public \
  --source=. \
  --remote=origin \
  --push
```

## 6. Create a tagged release

After validating the public repository:

```bash
git tag -a v1.0.0 -m "First reproducible public release"
git push origin v1.0.0
```

On GitHub, create a Release from that tag and describe:

- tested ndnSIM commit;
- included experiments (E1 and E4);
- default 20-run matrix;
- important compatibility notes;
- whether raw result archives are attached separately.

## 7. Recommended GitHub topics

```text
ndnsim
ns-3
named-data-networking
ndn
mobile-edge-computing
mec
digital-twin
age-of-information
caching
reproducible-research
```

## 8. What to archive with a paper

For reproducibility, preserve:

- the Git commit/tag used for the paper;
- `paper-experiment-config.json`;
- `experiment-matrix.csv`;
- `pairing-validation.csv`;
- aggregate CSVs;
- figure-generation script;
- optionally the full raw result directory in a release asset or archival repository.
