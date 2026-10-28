# Public demo hosting

The [GitHub Pages demo](https://logannye.github.io/bci-regression-workbench/) opens the saved human MINDFUL T11 comparison. The completed [Indy macaque report](https://logannye.github.io/bci-regression-workbench/indy/) remains available with its original bytes. Neither report requires installation, an account, an upload, or model execution.

## Publication boundary

Only six reviewed files in `site/` are deployed: `index.html`, `session_metrics.csv`, and `publication.json`, with the same three filenames under `indy/`.

- Each HTML page is the generated report plus one marked hosting notice containing attribution, license, scope, and evidence links. It includes bounded derived sample previews and error traces.
- Each CSV contains unchanged aggregate session scores from its frozen experiment.
- Each publication receipt records source revisions and content identities for that snapshot.

Raw neural recordings, complete labels/predictions, models, and full scoring bundles are excluded. The [human reproduction guide](human-demo/REPRODUCE.md) and [Indy reproduction guide](public-demo/REPRODUCE.md) describe their separate evidence workflows. The hosted pages are inspectable reports, not replacements for the scoring bundles.

Removing the single `PUBLIC-DEMO-NOTICE` block recovers the exact source report. The human report's SHA-256 is `4f46058f77847b29f3db1834fd02777de520f8739636e4cc7b8f2af7e90aafcb`; the Indy report's is `791b5eb1af655f3e816f49a91851f88ca0db0f8c884ba7f2f6506f8359da7bba`. All three files under `indy/` are byte-identical to the previous root publication at `b5869bbca061af34ca5ed427b7bd28d6f5c98850`. Original source-bound bundles remain intact. The human page was refreshed from the original saved predictions for a copy-only presentation review; [the receipt](validation/presentation-clarity-v1.json) verifies unchanged inputs, scores, and selection windows.

The human notice credits Pun et al. (2024), *Measuring instability in chronic human intracortical neural recordings towards stable, long-term brain-computer interfaces*, [Dryad DOI 10.5061/dryad.n2z34tn5s](https://doi.org/10.5061/dryad.n2z34tn5s), CC0-1.0. It labels the targets as inferred cursor-to-target displacement, describes the derived processing, and links the frozen plan and results. Lower offline proxy error does not establish better live control; the released neural features include noncausal processing.

The Indy notice retains O'Doherty, Cardoso, Makin, and Sabes, *Nonhuman Primate Reaching with Multichannel Sensorimotor Cortex Electrophysiology*, Zenodo v2, [DOI 10.5281/zenodo.3854034](https://doi.org/10.5281/zenodo.3854034), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Both notices identify the independent project relationship.

## Deployment

The repository uses GitHub Pages with **GitHub Actions** as the publishing source. The [Pages workflow](../.github/workflows/pages.yml) validates pull requests and deploys only from `main`. It uploads only `site/` and never executes either recording producer. A merge affecting the site, validator, or Pages workflow automatically publishes the reviewed snapshot. A manual workflow dispatch from `main` can republish it.

The workflow follows GitHub's [custom Pages workflow](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages), uses pinned official actions, and grants Pages/OIDC write permissions only to the deployment job.

Before updating a snapshot:

1. Obtain a separately validated public report. Preserve original bundles and frozen scientific decisions; do not refit models as part of publication.
2. Review its intended public previews and provenance. Retain attribution and clearly identify hosting additions.
3. Update the corresponding publication receipt and, only for an intentionally replaced report, the source-report identity in the validator. Do not refresh hashes merely to suppress an unexplained failure.
4. Run `python3 scripts/check_public_site.py`. It checks the six-file boundary, exact original reports, frozen session CSVs, fragments, attribution, target semantics, and absence of external assets or private paths. It validates these specific reviewed snapshots, not arbitrary data.
5. Preview desktop/mobile session selection and disclosures, then merge after hosted checks pass. Confirm deployment and the live URL.

Local publication checks and hosted CI do not imply Neuralink integration, intended-engineer usability validation, or a new scientific result. Human browser and software acceptance is recorded in [the validation receipt](human-demo/validation-v1.json); the recording experiment remains bound to its separately recorded source.
