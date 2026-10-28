# Sources and assumptions

Public sources reviewed on October 28, 2026. These establish the intended audience and available interfaces, not a request from Neuralink to build this tool.

| Source | What it supports |
| --- | --- |
| [Neuralink Machine Learning Engineer](https://job-boards.greenhouse.io/neuralink/jobs/5663271003) | Model-update evaluation infrastructure is a stated engineering responsibility. |
| [Neuralink datarepo announcement](https://neuralink.com/updates/datarepo/) | Neuralink uses the catalog in its data platform and welcomes extensions. The release does not include Neuralink recordings. |
| [datarepo repository](https://github.com/neuralinkcorp/datarepo) | The upstream library this project intends to use for its narrow data access and result cataloging path. |
| [datarepo user guide](https://data-repo.io/user-guide/) | Existing table, catalog, and schema-version interfaces. |
| [datarepo API](https://data-repo.io/api-docs/) | Existing Parquet and Delta interfaces, including transaction-version access that should be reused where applicable. |

## Design choices made here

The single velocity task, RMSE definition, fixed-model scope, plain-file output, and public-data demonstration are project decisions. They are not published Neuralink evaluation requirements.

We do not know the team's internal recording schema, decoder interface, existing regression tooling, or preferred error thresholds. The initial demonstration will use an explicit open contract and state what would need mapping for an internal trial.

The adoption hypothesis is that an engineer values a reproducible session-level regression report that complements their existing workflow. A conversation or evaluation by those engineers would be needed to establish that the hypothesis holds. No such validation has occurred.
