import json
import csv
import os

# region setup
with open('_config.json') as fl:
	config = json.load(fl)

with open('_schemas.json') as fl:
	schema = json.load(fl)['units']

LNG = config['setup']['LNG']

flnames = ''
flnames_en = config['inputs']['en']['units']
flnames_jp = config['inputs']['jp']['units']
# endregion

names = [schema['name']]


def read_stuff(lng:str):
	if (lng == 'en'):
		flnames = flnames_en
	else:
		flnames = flnames_jp

	for filename in filter(lambda x: x.startswith('Unit_Explanation'), os.listdir(flnames['name'])): 
		unit_ID = int(filename.removeprefix('Unit_Explanation').partition('_')[0])

		if(lng == 'en'):
			with open(flnames['name']+filename, encoding='utf-8', newline='') as fl:
				rows = list(csv.reader(fl, delimiter='|'))
		else:
			with open(flnames['name']+filename, encoding='utf-8', newline='') as fl:
				rows = list(csv.reader(fl))

		if (unit_ID-1 in [x[0] for x in names]):
			# ignore dupes
			continue

		curr = [unit_ID-1]
		prev = ''
		for row in rows[:3]: # 3 = formcount
			curr.append(row[0].strip() if row[0] != prev else '')
			prev = row[0]

		if (curr[1].strip() != "" and not curr[1][0:-2].isnumeric()):
			names.append(curr)

read_stuff('en')
read_stuff('jp')

names[1:] = sorted(names[1:])

with open(config['outputs']['units'], 'w', encoding='utf-8', newline='') as fl:
	w = csv.writer(fl, delimiter = '\t')
	w.writerows(names)