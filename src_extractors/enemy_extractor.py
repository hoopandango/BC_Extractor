import csv

import pandas as pd

from src_extractors.base import config

def extract():
	flnames_en = config['inputs']['en']['enemies']
	flnames_jp = config['inputs']['jp']['enemies']
	
	print("Started extracting enemies")
	with open(flnames_en['name'], encoding='utf-8', newline='') as fl:
		enemies_en = fl.read().split('\n')
	with open(flnames_jp['name'], encoding='utf-8', newline='') as fl:
		enemies_jp = fl.read().split('\n')
	enemies_existing = pd.read_csv(config['outputs']['enemies'], keep_default_na=False, delimiter='\t', index_col=0, quotechar='|').to_dict(orient='index')

	towrite = [['enemy_ID', 'enemy_name']]
	for i, name in enumerate(enemies_en):
		if name == '' or name == 'ダミー':  # ponos puts jp dummy value in en file because they hate me
			if enemies_jp[i] == 'ダミー':
				enemy = enemies_existing.get(i)
				if enemy is not None:
					name = enemy['enemy_name']
				else:
					name = 'Unknown'
			else:
				name = enemies_jp[i]
		towrite.append([i, name.strip()])
	
	with open(config['outputs']['enemies'], mode='w', encoding='utf-8', newline='') as fl:
		wr = csv.writer(fl, delimiter='\t', quotechar='|')
		wr.writerows(towrite)
		
	print('Finished Extracting enemies')

if __name__ == "__main__":
	extract()
