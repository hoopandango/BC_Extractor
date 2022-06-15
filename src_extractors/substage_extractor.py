import csv
import os
from src_extractors.base import config

prefixes = {'N': 0, 'S': 1000, 'C': 2000, '0': 3000, '1': 3003, '2': 3006, 'E': 4000, 'T': 6000, 'V': 7000, 'R': 11000, 'M': 12000, 'NA': 13000, 'B': 14000, 'D': 16000, 'A': 24000, 'H': 25000, 'CA': 27000, 'DM': 30000, 'Q': 31000}

sm_map = [45, 44, 43, 42, 41, 40, 39, 38, 37, 36, 35, 34, 33, 32, 31, 30, 29, 28, 27, 26, 25, 24, 23, 22, 21, 20, 19, 18, 17, 16, 15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0, 46, 47, 48, 49, 50]

def extract():
	flnames_en = config['inputs']['en']['substages']
	flnames_jp = config['inputs']['jp']['substages']
	
	ss_dict = {}
	
	for _fpjp, _fpen in zip(os.listdir(flnames_jp['name']), os.listdir(flnames_en['name'])):
		fpen = os.path.join(flnames_en['name'], _fpen)
		fpjp = os.path.join(flnames_jp['name'], _fpjp)
		
		pre = _fpen.removeprefix('StageName').removesuffix('en.csv').replace('_', '').removeprefix('R')
		stageset_ID = prefixes.get(pre)
		if stageset_ID is None:
			continue
		
		with open(fpjp, encoding='utf-8', newline='') as fljp, open(fpen, encoding='utf-8', newline='') as flen:
			rows_jp = list(csv.reader(fljp, delimiter=','))
			rows_en = list(csv.reader(flen, delimiter='|'))
		
		if pre.isnumeric():
			for stage_ID, substages in enumerate(rows_en):
				for i in range(1, 4):
					ID = (stageset_ID + i - 1) * 100 + sm_map[stage_ID]
					ss_dict[ID] = substages[0].strip()
				for i in range(1, 4):
					ID = (20_000 + 1_000 * int(pre)) * 100 + (i - 1) * 100 + sm_map[stage_ID]
					ss_dict[ID] = substages[0].strip()
			continue  # this is only for story mode shit
		
		for stage_ID, substages in enumerate(rows_jp):
			for substage_ID, substage in enumerate(substages):
				ID = stageset_ID * 100 + stage_ID * 100 + substage_ID
				if (substage.strip() not in ("", "@", "＠")):
					ss_dict[ID] = substage.strip()
		
		for stage_ID, substages in enumerate(rows_en):
			for substage_ID, substage in enumerate(substages):
				ID = stageset_ID * 100 + stage_ID * 100 + substage_ID
				if (substage.strip() not in ("", "@", "＠")):
					ss_dict[ID] = substage.strip()
	
	buf = "substage_ID\tsubstage_name\n"
	for key, value in sorted(list(ss_dict.items()), key=lambda x: x[0]):
		buf += str(key) + "\t" + value + "\n"
	with open(config['outputs']['substages'], 'w', encoding='utf-8', newline='') as fl:
		fl.write(buf)
	print("Finished extracting substages")
	return
	
if __name__ == "__main__":
	extract()
