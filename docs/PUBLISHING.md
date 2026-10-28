# Public demo hosting

The [GitHub Pages demo](https://logannye.github.io/bci-regression-workbench/) opens directly into the redesigned, saved Indy report. No installation, account, data upload, or model execution is involved.

## Publication boundary

Only three reviewed files in `site/` are deployed:

- `index.html`: the validated public report, plus a marked hosting notice with dataset attribution, license, scope, and evidence links. It includes the report's bounded derived sample previews and error traces.
- `session_metrics.csv`: the unchanged aggregate session scores from the frozen experiment.
- `publication.json`: source revision and content identities for this snapshot.

Raw neural recordings, complete labels/predictions, models, and the full scoring bundle are not in the site. The [reproduction guide](public-demo/REPRODUCE.md) describes the separate evidence workflow. The hosted page is an inspectable report, not a replacement for that bundle.

The current localized report snapshot has SHA-256 `791b5eb1af655f3e816f49a91851f88ca0db0f8c884ba7f2f6506f8359da7bba`. Removing the single `PUBLIC-DEMO-NOTICE` block from the hosted HTML recovers those exact bytes, including its script, session rows, charts, and provenance. Scoring source is unchanged; the renderer adds the documented fixed-window localization. The original source-bound bundles remain intact.

The dataset attribution appears in the page's **About this demo & dataset** disclosure: O'Doherty, Cardoso, Makin, and Sabes, *Nonhuman Primate Reaching with Multichannel Sensorimotor Cortex Electrophysiology*, Zenodo v2, [DOI 10.5281/zenodo.3854034](https://doi.org/10.5281/zenodo.3854034), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The notice identifies the derived processing and independent project relationship.

## Deployment

The repository uses GitHub Pages with **GitHub Actions** as the publishing source. The [Pages workflow](../.github/workflows/pages.yml) validates on pull requests and deploys only from `main`. It uploads only `site/`; it never executes the public recording producer. A merge affecting the site, validator, or Pages workflow automatically publishes the reviewed snapshot. A manual workflow dispatch from `main` can republish it.

The workflow follows GitHub's [custom Pages workflow](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages), uses pinned official actions, and grants Pages/OIDC write permissions only to the deployment job.

Before updating the snapshot:

1. Obtain a separately validated public report. Preserve original bundles and frozen scientific decisions; do not refit models as part of publication.
2. Review its intended public previews and provenance. Keep dataset attribution and clearly identify any hosting additions.
3. Update the reviewed file identities in `site/publication.json` and, only for an intentionally replaced report, the original-report identity in the validator. Do not merely refresh hashes to suppress an unexplained failure.
4. Run `python3 scripts/check_public_site.py`. It verifies the three-file boundary, exact original report, frozen session CSV, fragment links, attribution, and lack of external assets or private paths. This is a check of this specific reviewed snapshot, not a general data sanitizer.
5. Preview desktop/mobile session selection and disclosures, then merge after hosted checks pass. Confirm the Pages deployment and inspect the live URL.

Local publication checks and hosted CI do not imply Neuralink integration, intended-engineer usability validation, or a new scientific result.
