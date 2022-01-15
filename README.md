# BC Extractors

## **v 0.5.1**

This repository contains the files and code that I use to produce automated event data.

## Project Tree

```plaintext
📦root
 ┣ 📂extras
 ┣ 📂latest_en
 ┣ 📂latest_jp
 ┣ 📂out_intermediates
 ┣ 📂outputs
 ┣ 📂reusables
 ┣ 📂tests
 ┣ 📜_config.json
 ┣ 📜_schemas.json
 ┣ 📜.gitignore
 ┣ 📜combo_extractor.py
 ┣ 📜event_data_fetchers.py
 ┣ 📜event_data_parsers.py
 ┣ 📜event_data_printers.py
 ┣ 📜gatya_extractor.py
 ┣ 📜items_extractor.py
 ┣ 📜README.md
 ┣ 📜sale_extractor.py
 ┣ 📜talent_extractor.py
 ┣ 📜units_extractor.py
 ┣ 📜utils.py
 ┗ 📜z_downloaders.py
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

* **v 0.1** - just added the code here for the sake of it. Only a few TODOs in here. More will follow. Planning on a lot more comments too.
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