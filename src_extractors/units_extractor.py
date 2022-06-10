import csv
import os

import pandas as pd

from src_extractors.base import config, schemas

def extract():
	schema = schemas['units']
	flnames_en = config['inputs']['en']['units']
	flnames_jp = config['inputs']['jp']['units']

	names = [schema['name']]
	descriptions = [schema['desc']]

	def read_stuff(lng: str):
		if (lng == 'en'):
			flnames = flnames_en
		else:
			flnames = flnames_jp
		
		for filename in filter(lambda x: x.startswith('Unit_Explanation'), os.listdir(flnames['name'])):
			unit_ID = int(filename.removeprefix('Unit_Explanation').partition('_')[0])
			
			if (lng == 'en'):
				with open(flnames['name'] + filename, encoding='utf-8', newline='') as fl1:
					rows = list(csv.reader(fl1, delimiter='|'))
			else:
				with open(flnames['name'] + filename, encoding='utf-8', newline='') as fl1:
					rows = list(csv.reader(fl1))
			
			if (unit_ID - 1 in [x[0] for x in names]):
				# ignore dupes
				continue
			
			curr = [unit_ID - 1]
			currdesc = []
			prev = ''
			for i, row in enumerate(rows[:3]):  # 3 = formcount
				curr.append(row[0].strip() if row[0] != prev else '')
				currdesc.append([unit_ID-1, i, ("\n".join(row[1:])).strip() if row[0] != prev else ''])
				prev = row[0]
			
			if (curr[1].strip() != "" and not curr[1][0:-2].isnumeric()):
				names.append(curr)
				descriptions.extend(currdesc)
	
	print("Started extracting units")
	read_stuff('en')
	read_stuff('jp')

	names[1:] = sorted(names[1:])
	dfnames = pd.DataFrame(names[1:]).set_index(0)
	descriptions[1:] = sorted(descriptions[1:])
	buf = ""
	prev=-1
	for desc in descriptions[1:]:
		if desc[0] != prev:
			buf += f"\n{desc[0]}\n"
			prev = desc[0]
		unitname = dfnames.loc[desc[0]].iloc[desc[1]]
		if unitname != '':
			buf += f"[{unitname}]\n{desc[2]}\n"

	with open(config['outputs']['units'], 'w', encoding='utf-8', newline='') as fl:
		w = csv.writer(fl, delimiter='\t')
		w.writerows(names)
		
	with open(config['outputs']['descriptions'], 'w', encoding='utf-8', newline='') as fl:
		fl.write(buf)

	print("Finished extracting units")
	
if __name__ == "__main__":
	extract()
