import json

with open('_config.json') as fl:
	config = json.load(fl)

with open('_schemas.json') as fl:
	schemas = json.load(fl)
