[![Discord](https://img.shields.io/badge/chat-on%20discord-7289da.svg?sanitize=true)](https://discord.gg/GUAy9wErNu)
[![](https://img.shields.io/discord/908084610158714900)](https://discord.gg/GUAy9wErNu)
[![Static Badge](https://img.shields.io/badge/github-assemblyline-blue?logo=github)](https://github.com/CybercentreCanada/assemblyline)
[![Static Badge](https://img.shields.io/badge/github-assemblyline--mcp-blue?logo=github)](https://github.com/CybercentreCanada/assemblyline-mcp)
[![GitHub Issues or Pull Requests by label](https://img.shields.io/github/issues/CybercentreCanada/assemblyline/mcp)](https://github.com/CybercentreCanada/assemblyline/issues?q=is:issue+is:open+label:mcp)
[![License](https://img.shields.io/github/license/CybercentreCanada/assemblyline-mcp)](./LICENCE.md)

# Assemblyline 4 - MCP

This repository provides the Model Context Protocol (MCP) server for Assemblyline.

## Submit a file by hash

The `submit_by_hash` tool creates a submission using a hash or configured file-source
identifier without uploading file contents. It supports SHA-256, SHA-1, MD5, TLSH,
ssdeep, and custom input types advertised by the Assemblyline instance. The file must
be available to Assemblyline or retrievable through its selected external sources.

| Argument | Description |
| --- | --- |
| `file_hash` | Required hash or identifier matching the selected input type's configured pattern. MD5, SHA-1, and SHA-256 are case-insensitive; other inputs retain their original case. |
| `hash_type` | Input type, defaulting to `sha256` for compatibility. Specify `md5`, `sha1`, `tlsh`, `ssdeep`, or a configured custom type for other inputs. |
| `fname` | Optional filename; defaults to the hash. |
| `params` | Optional submission parameters, such as `services`, `ignore_cache`, or `default_external_sources` (a list of source names). |
| `metadata` | Optional submission metadata. |
| `submission_profile` | Optional Assemblyline submission profile name. |

Example tool arguments (existing SHA-256 calls are unchanged):

```json
{
  "file_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "fname": "sample.bin",
  "metadata": {"source": "mcp"}
}
```

For other input types, call `system_configuration` and inspect
`submission.file_sources`. This maps input types to their `pattern`, available
`sources`, and `auto_selected` source names. The tool validates the input against
the current user's advertised configuration before submitting it with the client's
`fetch_input` API. Unknown types and mismatched values produce tool errors.

For example, to submit an MD5 using a source named `VirusTotal`, if that source is
configured and available to the user:

```json
{
  "file_hash": "d41d8cd98f00b204e9800998ecf8427e",
  "hash_type": "md5",
  "params": {"default_external_sources": ["VirusTotal"]}
}
```

Custom types use the same arguments: for example, `hash_type: "ticket"` and
`file_hash: "CASE-123"` if the instance advertises a matching ticket source. A source
can also define a URL-like input type; use its advertised type name and pattern.
The MCP server does not download the input itself or configure new sources.

Omitting `params.default_external_sources` uses the user's source defaults. An empty
list also falls back to those defaults; it does not disable external fetching.
Assemblyline first checks its existing files where supported, then evaluates eligible
selected sources in configuration order until one succeeds. Source access controls,
classification, metadata, service selection, and direct-download versus AL-URI behavior
remain enforced by Assemblyline. See [File Sources](https://cybercentrecanada.github.io/assemblyline4_docs/installation/configuration/submission/#file-sources).

The tool uses the current request's API key or OAuth token and respects Assemblyline's
submission permissions, defaults, and quotas. API errors are returned as tool errors.
The response contains the submission details, including `sid`, which can be passed
to `get_submission` to retrieve its status. Repeated calls create new submissions;
existing analysis results may be reused unless submission parameters specify otherwise.

## Image variants and tags

| **Tag Type** | **Description**                                                                                  |      **Example Tag**       |
| :----------: | :----------------------------------------------------------------------------------------------- | :------------------------: |
|    latest    | The most recent build (can be unstable).                                                         |          `latest`          |
|  build_type  | The type of build used. `dev` is the latest unstable build. `stable` is the latest stable build. |     `stable` or `dev`      |
|    series    | Complete build details, including version and build type: `version.buildType`.                   | `4.5.stable`, `4.5.1.dev3` |

## Documentation

For more information about service development for Assemblyline, follow this [guide](https://cybercentrecanada.github.io/assemblyline4_docs/developer_manual/services/developing_an_assemblyline_service/).

---

# Assemblyline 4 - MCP

Ce référentiel fournit les fonctionnalités de base des services Assemblyline 4.

## Soumettre un fichier par hachage

L'outil `submit_by_hash` crée une soumission à partir d'un hachage ou d'un identifiant
de source configurée, sans téléverser le contenu du fichier. Il prend en charge
SHA-256, SHA-1, MD5, TLSH, ssdeep et les types personnalisés annoncés par l'instance.
Le fichier doit être disponible dans Assemblyline ou récupérable à partir des
sources externes sélectionnées.

| Argument | Description |
| --- | --- |
| `file_hash` | Hachage ou identifiant obligatoire conforme au motif du type sélectionné. MD5, SHA-1 et SHA-256 sont insensibles à la casse; les autres valeurs conservent leur casse. |
| `hash_type` | Type d'entrée, `sha256` par défaut. Préciser `md5`, `sha1`, `tlsh`, `ssdeep` ou un type personnalisé configuré pour les autres entrées. |
| `fname` | Nom de fichier facultatif; le hachage est utilisé par défaut. |
| `params` | Paramètres facultatifs, tels que `services`, `ignore_cache` ou `default_external_sources` (liste de noms de sources). |
| `metadata` | Métadonnées de soumission facultatives. |
| `submission_profile` | Nom facultatif d'un profil de soumission Assemblyline. |

Consulter `submission.file_sources` dans la réponse de `system_configuration` pour
découvrir les types, leurs motifs de validation (`pattern`), les sources disponibles
(`sources`) et les sources présélectionnées (`auto_selected`). L'outil valide l'entrée
selon cette configuration avant de la soumettre via `fetch_input`. Un type inconnu
ou une valeur non conforme produit une erreur d'outil.

Les appels SHA-256 existants restent inchangés. Pour un MD5, préciser
`hash_type: "md5"` et, si nécessaire, `params.default_external_sources`, par exemple
`["VirusTotal"]` si cette source est disponible. Un type personnalisé, tel que
`ticket` avec la valeur `CASE-123`, doit être annoncé par l'instance. Les types
personnalisés peuvent également représenter des URL.

L'absence de `default_external_sources`, comme une liste vide, utilise les sources
par défaut de l'utilisateur. Assemblyline évalue les sources admissibles dans l'ordre
de configuration jusqu'au premier succès. Les contrôles d'accès, la classification,
les métadonnées, la sélection des services et le mode de récupération restent gérés
par Assemblyline. Voir [File Sources](https://cybercentrecanada.github.io/assemblyline4_docs/installation/configuration/submission/#file-sources).

L'outil utilise la clé API ou le jeton OAuth de la requête et respecte les
autorisations, les paramètres par défaut et les quotas d'Assemblyline. Les erreurs
de l'API sont renvoyées comme erreurs d'outil. La réponse contient les détails de
la soumission, dont `sid`, utilisable avec `get_submission` pour consulter son état.
Chaque appel crée une nouvelle soumission; les résultats d'analyse existants peuvent
être réutilisés, sauf indication contraire dans les paramètres de soumission.

## Variantes et étiquettes d'image

| **Type d'étiquette** | **Description**                                                                                                  |  **Exemple d'étiquette**   |
| :------------------: | :--------------------------------------------------------------------------------------------------------------- | :------------------------: |
|       dernière       | La version la plus récente (peut être instable).                                                                 |          `latest`          |
|      build_type      | Le type de compilation utilisé. `dev` est la dernière version instable. `stable` est la dernière version stable. |     `stable` or `dev`      |
|        séries        | Le détail de compilation utilisé, incluant la version et le type de compilation : `version.buildType`.           | `4.5.stable`, `4.5.1.dev3` |

## Documentation

Pour plus d'informations sur le développement des services pour Assemblyline, suivez ce [guide](https://cybercentrecanada.github.io/assemblyline4_docs/developer_manual/services/developing_an_assemblyline_service/).
