import json
import pandas as pd
import csv
import sqlite3
from collections import Counter, defaultdict

import sys

# region setup
from local_readers import Readers

with open('_config.json') as fl:
	config = json.load(fl)

sys.stdout = open(config["outputs"]["gatya_text"], 'w', encoding='utf-8')

with open('_schemas.json') as fl:
	schema = json.load(fl)['gatya']

LNG = config['setup']['LNG']

flnames_jp = config['inputs']['jp']['gatya']
fl_out = config['outputs']['gatya']

with open(flnames_jp["data"], encoding='utf-8') as fl:
	rd = csv.reader(fl)
	gatya_info = [[int(x) for x in row[0:row.index('-1')]] for row in rd if '-1' in row]

with open(flnames_jp["option"], encoding='utf-8') as fl:
	options = pd.read_csv(fl, delimiter='\t', index_col=0)

try:
	conn = sqlite3.connect(fl_out)
except sqlite3.OperationalError:
	print("db not found")
	raise Exception

series = pd.read_sql('SELECT * FROM series', conn, index_col='series_ID')

series["head"] = [-1]*len(series)

conn.close()

"""
def lookup(searched:str)->int:
	for unit in unit_names.iterrows():
		if searched in list(unit[1]):
			return unit[0]  # unit ID
	return -1
"""
"""
default_units = {"Cutter Cat":"Grandon","Neneko":"Neneko&Friends","Freshman Cat Jobs":"Reinforcements"}
blacklist = {"Freshman Cat Jobs", "Rich Cat III", "Sniper the Recruit", "Cat Base Mini", "Gold Cat", "Neneko",
"Metal Cat", "Driller Cat", "Piledriver Cat", "Cutter Cat", "Backhoe Cat", "Miter Saw Cat"}
"""
default_units = {445: 'D', 131: 'N', 237: 'R'}
blacklist = {129, 131, 200, 237, 238, 239, 144, 443, 444, 445, 446, 447}
headbackups = [-1] * len(series)

def get_SID(ID: int) -> int:
	return options.loc[ID, "seriesID"]

def is_enabled(ID: int) -> bool:
	return (options.loc[ID, "BannerON_OFF"] == 1)

def get_exclusives(gatya: list) -> list:
	toret = []
	
	for unit in gatya:
		k = default_units.get(unit)
		if k is not None: toret.append(k)
	
	return list(set(toret))

def get_series(s_ID: int) -> str:
	return series.loc[s_ID, "series_name"]

def set_head(s_ID: int, ID: int) -> None:
	"""for backchecker version
	headbackups[s_ID] = series.loc[s_ID,"head"]
	"""
	series.loc[s_ID, "head"] = ID


def get_head(s_ID: int) -> int:
	try:
		return series.loc[s_ID, "head"]
	except KeyError:
		series.loc[s_ID] = ["Placeholder", -1]
		return series.loc[s_ID, "head"]

def diff_gatya(new: list, old: list) -> list:
	return [set(new) - set(old) - blacklist, set(old) - set(new) - blacklist]

def bonus_check(gatya: list):
	freqs = Counter(gatya)
	toret = defaultdict()
	for K, V in freqs.items():
		toret.setdefault(V, []).append(K)
	del (toret[1])
	return toret

df_main = pd.DataFrame(columns=schema['main']).set_index(schema['main'][0])
json_data = {}
df_units = pd.DataFrame(columns=schema['units']).set_index(schema['units'][0])

row = [0, 0, 0, 0]
# Processes all gatya


def process_all():
	for (ID, gatya) in enumerate(gatya_info):
		s_ID = get_SID(ID)
		prev = get_head(s_ID)
		serie = get_series(s_ID)
		excl = get_exclusives(gatya)
		
		# Print previous banner in the series, if existent
		if (prev == -1):
			set_head(s_ID, ID)
			diff = [[], []]
		else:
			diff = diff_gatya(gatya, gatya_info[prev])
		
		# normal version
		print(str(ID) + '\t', end='')
		if (prev != -1):
			if len(diff[0]) == len(diff[1]) == 0:
				print(f"(≅ {prev})", end='')
			else:
				json_data[prev]["diff"] = [[], []]
				set_head(s_ID, ID)
				print(f"(> {prev})", end='')
		
		""" funky backchecker version
		if(prev != -1):
			if len(diff[0]) == len(diff[1]) == 0:
				prev = headbackups[s_ID]
				diff = diff_gatya(gatya,gatya_info[prev])
			else:
				set_head(s_ID,ID)
			print(f"(> {prev})",end='')
		"""
		
		print(f"\t{serie}\t", end='')
		
		# Get banner exclusives
		if excl != []:
			print(f" [{' + '.join(excl)}]", end='')
		
		# Diff from previous banner:
		if (len(diff[0]) > 0):
			diff[0] = [Readers.getCat(i, 0) for i in diff[0]]
			if (len(diff[0]) < 6):
				
				print(f" (+ {', '.join(diff[0])})", end='')
			else:
				print(f" (+ a lot)", end='')
		if (len(diff[1]) > 0):
			diff[1] = [Readers.getCat(i, 0) for i in diff[1]]
			if (len(diff[1]) < 6):
				print(f" (- {', '.join(diff[1])})", end='')
			else:
				print(f" (- a lot)", end='')
		
		bonuses = bonus_check(gatya)
		bonuses = {K: [Readers.getCat(X, 0) for X in V] for (K, V) in bonuses.items()}
		if (len(bonuses) > 0):
			print(" {" + ", ".join([f"{K}x rate on {', '.join(V)}" for (K, V) in bonuses.items()]) + "}", end='')
		
		print()
		
		# END OF PRINTING
		# "banner_ID" -> "banner_name","exclusives","rate_ups","diff+","diff-","enabled","series_ID"
		# "banner_ID" -> "units_in_banner"
		row = [serie, str(excl), str(dict(bonuses)), str([list(diff[0]), list(diff[1])]), is_enabled(ID), s_ID]
		
		df_main.loc[ID] = row
		
		row_comp = {"banner_name": str(serie), "enabled": bool(is_enabled(ID)), "series_ID": int(s_ID)}
		if (len(excl) | 1):
			row_comp["exclusives"] = excl
		if (len(diff) | 1):
			row_comp["diff"] = [list(diff[0]), list(diff[1])]
		if (len(bonuses) | 1):
			row_comp["rate_ups"] = bonuses
		
		json_data[ID] = row_comp
		
		row = str([Readers.getCat(x, 0) for x in gatya])
		df_units.loc[ID] = row

process_all()

# Export management

conn = sqlite3.connect(fl_out)

series.to_sql('series', conn, if_exists='replace', index=True)
df_main.to_sql('main', conn, if_exists='replace', index=True)

with open(config["outputs"]["gatya_json"], 'w', encoding='utf-8') as fl:
	json.dump(json_data, fl, ensure_ascii=False, indent=2)
df_units.to_sql('units', conn, if_exists='replace', index=True)

sys.stdout.close()
conn.close()
input()