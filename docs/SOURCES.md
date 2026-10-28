# Sources and assumptions

Public sources reviewed on October 28, 2026. These establish the intended audience and available interfaces, not a request from Neuralink to build this tool.

| Source | What it supports |
| --- | --- |
| [Neuralink Machine Learning Engineer](https://job-boards.greenhouse.io/neuralink/jobs/5663271003) | Model-update evaluation infrastructure is a stated engineering responsibility; the listed ML/backend stack includes PyTorch, JAX, and Python. |
| [Neuralink datarepo announcement](https://neuralink.com/updates/datarepo/) | Neuralink uses the catalog in its data platform and welcomes extensions. The release does not include Neuralink recordings. |
| [datarepo repository](https://github.com/neuralinkcorp/datarepo) | The upstream library this project intends to use for its narrow data access and result cataloging path. |
| [datarepo user guide](https://data-repo.io/user-guide/) | Existing table, catalog, and schema-version interfaces. |
| [datarepo API](https://data-repo.io/api-docs/) | Existing Parquet and Delta interfaces, including transaction-version access that should be reused where applicable. |

## Design choices made here

The output-first Python interface, single velocity task, RMSE definition, pinned baseline, local report, and public-data demonstration are project decisions. They are not published Neuralink evaluation requirements.

We do not know the team's internal recording schema, evaluator, experiment tracker, existing regression tooling, or preferred error thresholds. We also do not know whether its BCI evaluation jobs use datarepo directly. The workflow described here is an integration hypothesis; the public example will expose the exact output mapping to validate.

The adoption hypothesis is that an engineer values a reproducible session-level regression report that complements their existing workflow. A conversation or evaluation by those engineers would be needed to establish that the hypothesis holds. No such validation has occurred.
