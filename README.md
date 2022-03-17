# BC Extractors

## **v 2.0.2**

This repository contains the files and code that I use to produce automated event data.

## Project Tree

`*` means not included in the repository

```plaintext
📦BC_Extractor
 ┣ 📂extraction
 ┃ ┣ * 📜decrypt.py
 ┃ ┗ 📜__init__.py
 ┣ 📂extras
 ┃ ┣ 📜EventGroups.json
 ┃ ┣ 📜Events.tsv
 ┃ ┗ 📜Missions.tsv
 ┣ 📂outputs
 ┃ ┣ *📂eventdata
 ┃ ┃ ┣ 📜events_processed.db
 ┃ ┃ ┣ 📜export.json
 ┃ ┃ ┣ 📜gatya_final.txt
 ┃ ┃ ┣ 📜gatya_processed.db
 ┃ ┃ ┣ 📜gatya_raw.json
 ┃ ┃ ┣ 📜output.txt
 ┃ ┃ ┗ 📜stages_raw.json
 ┃ ┣ 📜catcombos.db
 ┃ ┣ 📜gatya.db
 ┃ ┗ 📜talents.db
 ┣ 📂out_intermediates
 ┃ ┗ 📜catcombos.db
 ┣ 📂reusables
 ┃ ┣ 📜combos.tsv
 ┃ ┣ 📜enemies.tsv
 ┃ ┣ 📜events.tsv
 ┃ ┣ 📜gatya.json
 ┃ ┣ 📜gatya.txt
 ┃ ┣ 📜items.tsv
 ┃ ┣ 📜missions.tsv
 ┃ ┣ 📜sales.tsv
 ┃ ┣ 📜series.tsv
 ┃ ┣ 📜stages.tsv
 ┃ ┣ 📜substages.tsv
 ┃ ┗ 📜units.tsv
 ┣ 📂src
 ┃ ┣ 📜event_data_printers.py
 ┃ ┗ 📜__init__.py
 ┣ 📂src_backend
 ┃ ┣ 📜containers.py
 ┃ ┣ 📜event_data_fetchers.py
 ┃ ┣ 📜event_data_parsers.py
 ┃ ┣ 📜local_readers.py
 ┃ ┣ 📜utils.py
 ┃ ┣ 📜z_downloaders.py
 ┃ ┗ 📜__init__.py
 ┣ 📂src_extractors
 ┃ ┣ 📜combo_extractor.py
 ┃ ┣ 📜gatya_extractor.py
 ┃ ┣ 📜items_extractor.py
 ┃ ┣ 📜mission_extractor.py
 ┃ ┣ 📜sale_extractor.py
 ┃ ┣ 📜talent_extractor.py
 ┃ ┣ 📜units_extractor.py
 ┃ ┗ 📜__init__.py
 ┣ * 📂 tests - test cases that aren't used for anything
 ┣ * 📂 venv - python virtual environment
 ┣ 📜.gitignore
 ┣ 📜extract.py - calls all extracters internally
 ┣ 📜Procfile - starts the server
 ┣ * 📜Procfile.ps1 - starts the server [in windows]
 ┣ 📜README.md - this file
 ┣ 📜requirements.txt - tells python what modules are needed 
 ┣ 📜runtime.txt - tell what version of python is used
 ┣ 📜setup.py - same as above two files but like a bit different
 ┣ 📜testserver.py - runs django testing server for debugging stuff
 ┣ 📜_config.json - contains config information
 ┗ 📜_schemas.json - contains schemas of talbes
 ```

## **Overview**

* **extras** contains data files that are mostly human-maintained. These cannot be automated.
* **latest_en** and **latest_jp** contain data extracted from the latest version of Battle Cats. I am not adding them to this repo for both size and legality reasons. You only need resLocal and DataLocal folders from these, though.
* **out_intermediates** contain intermediates that need some human intervention mid-processing.
* **reusables** contain .tsv and .json format files, most of which are reused by some other program.
* **outputs** contains .db files or files that are not going to be reused by other programs.
* **tests** has test cases. I don't know how to do unit testing so I mostly plug them manually.
* **_config.json** and **_schemas.json** are configuration files. I don't know if it's good design to have them that way, but it sounds edgy so I did it.

The rest should hopefully have self-explanatory titles.

## **Changelog**

* **v 0.1.0** - just added the code here for the sake of it. Only a few TODOs in here. More will follow. Planning on a lot more comments too.
* **v 0.1.1** - added this README.
* **v 0.1.2** - patched duplicate merging bug, caused by popping elements in the container that I'm iterating over.
* **v 0.1.3** - fixed duplicate merging shenanigans for good. Added improved interpretation for monthly and weekly recurring events.
* **v 0.1.4** - reformatted code, removed unnecessary variables.
* **v 0.2.0** - ItemFetcher is now functional, added a draft of missions extractor[WIP]
* **v 0.2.1** - prepared templates for mission information.
* **v 0.2.2** - first draft of mission parsing, prepared, templates were functional. improved item_extractor to pick up item IDs of cats.
* **v 0.2.3** - shifted local file readers to their own file for cleaner organisation.
* **v 0.3.0** - heavy type hinting implemented for gatya.
* **v 0.3.1** - type hinting also added to stages, although not fully functional.
* **v 0.3.2** - patched data grouping bug. finished type hinting for ItemFetcher
* **v 0.3.3** - added local cache of foreign dependencies. Implemented aiohttp for faster queries.
* **v 0.4.0** - transferred print method to container classes to make printing easier. migrated all grouping to the groupData() function.
* **v 0.4.1** - bug fixes. added feature to API call for fetching name to not send a query to web if it's more appropriate that way.
* **v 0.5.0** - implemented basic data exporting as JSON file. not ironed out yet.
* **v 0.5.1** - improved festival data printing to rely on grouped festival data rather than guessing from refinedData.
* **v 1.0.0** - set up migration to Heroku. 
* **v 1.1.0** - configured authentication via environment variables.
* **v 1.2.0** - completed accepting queries through POST requests.
* **v 1.2.1** - started accepting text through diffs, refined query, minor bug fixes.
* **v 1.3.0** - gave ability to return coloured output [broken].
* **v 1.3.1** - fixed coloured output.
* **v 1.4.0** - supports writing to multiple webhooks. some formatting alterations and bug fixes alongside this.
* **v 1.4.1** - patched return message, had committed a test message into the repo because lul. updated project tree in README.
* **v 1.4.2** - stopped sending gatya / item / sale blocks if they're empty
* **v 1.5.0** - fixed how hooks are pulled out from env variables
* **v 1.5.1** - moved outputs to gitignore
* **v 1.6.0** - implemented logging
* **v 1.7.0** - implemented pinging via roles + tons of bug fixes
* **v 1.7.1** - fixed deadly carnival name, dojo bug
* **v 1.7.2** - fixed missing stamp name bug, refactored folders, fixed gatya diff desync bug
* **v 1.8.0** - added support for 6 talents
* **v 1.8.1** - update-time bugs fall-over
* **v 1.8.2** - updated en data, removed extractors
* **v 1.9.0** - added removed event display feature. fixed substages.tsv
* **v 1.10.0** - fixed caching to make it efficient, added two-layer-cache for stages that uses BCU information as a backup
* **v 2.0.0** - fixed anomalous addition of placeholder sixth talents. put a bandage on floating points during catcombo extraction. standardised order for banner exclusives and diffs so we constructively infer information from gatya diffs. implemented LRU cache on web queries. fixed n * SoL mission detection bug. overhauled data extraction so that 90% of the process can be done with a single click.
* **v 2.0.1** - re-added extraction files to the repository for better archival
* **v 2.0.2** - updated README.