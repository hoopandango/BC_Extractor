import pandas as pd
import sqlite3
from pandas.core.frame import DataFrame
import json

gaps = None
def extract():
	sizes = ['UP Sm', 'UP M', 'UP L', 'UP XL']
	
	# region setup
	with open('_config.json') as fl:
		config = json.load(fl)
	
	with open('_schemas.json') as fl:
		schemas = json.load(fl)['combos']
	
	# Set true to save DB in CatBot format
	CBMODE = config['setup']['combos']['catbotmode']
	
	# special mode to import regular tables and convert them to catbot format
	LOADMODE = config['setup']['combos']['loadmode']
	
	# en - searches for only en files
	# jp - searches for both en and jp files
	LNG = config['setup']['LNG']
	
	schema_main = schemas['regular']['main']
	schema_units = schemas['regular']['units']
	schema_effects = schemas['regular']['effects']
	schema_sizes = schemas['regular']['sizes']
	
	# schema_CBunits = schemas['catbot']['units']
	schema_CBmain = schemas['catbot']['main']
	
	flnames_en = config['inputs']['en']['combos']
	flnames_jp = config['inputs']['jp']['combos']
	
	output = config['outputs']['combos']
	interm = config['intermediates']['combos']
	
	# endregion
	
	def invert_imp():
		config['setup']['combos']['loadmode'] = not LOADMODE
		with open('_config.json', mode='w') as fl1:
			json.dump(config, fl1, indent='\t')
	
	try:
		conn = sqlite3.connect(output)
	except sqlite3.OperationalError:
		print("Database for CatCombos not found")
		return
	
	try:
		conn2 = sqlite3.connect(interm)
	except sqlite3.OperationalError:
		print("Intermediate Database for CatCombos not found")
		return
	
	def get_combo_sizes_table() -> DataFrame:
		with open(flnames_en['sizes']) as fl1:
			tsze = pd.read_csv(fl1, header=None, delimiter='|')
		
		tsze = tsze.iloc[:, 0:1]
		tsze.columns = schema_sizes[1:]
		
		return tsze
	
	def get_combo_effects_table() -> DataFrame:
		with open(flnames_en['effects']) as fl1:
			teff = pd.read_csv(fl1, header=None, delimiter='|')
		
		teff = teff.iloc[:, 0:1]
		teff.columns = schema_effects[1:]
		
		return teff
	
	gaps = []
	
	def get_combo_units_table() -> DataFrame:
		if LNG == 'en':
			with open(flnames_en['data']) as fl1:
				df = pd.read_csv(fl1, header=None, delimiter=',', usecols=range(0, 15)).dropna()
		# elif LNG == 'jp':
		else:
			with open(flnames_jp['data']) as fl1:
				df = pd.read_csv(fl1, header=None, delimiter=',', usecols=range(0, 15)).dropna()
			
			df = df.append(df[gaps], ignore_index=True)
		
		# Usecols allows me to ignore stupid commas at the end of some rows but not others
		
		df = df[df[1] >= 0]  # Remove unused combos
		df.reset_index(inplace=True)
		
		tunt = pd.DataFrame(columns=schema_units[1:])
		
		for i in range(5):
			# 2i+2 => Base ID, 2i+3 => Form number
			tunt.iloc[:, i] = 3 * df[2 * i + 2] + df[2 * i + 3]  # Converts PONOS ID to CatBot ID
		
		tunt = tunt.applymap(lambda x: max(x, -1))  # Converts dummy slots to -1
		tunt = tunt.astype(int, errors='ignore')
		
		return tunt
	
	def get_combo_table() -> DataFrame:
		global gaps
		if LNG == 'en':
			with open(flnames_en['names'], encoding='utf-8') as fl_names:
				names: DataFrame
				names = pd.read_csv(fl_names, header=None, delimiter='|')
			names = names.iloc[:, 0:1]
			
			with open(flnames_en['data']) as fl_data:
				data = pd.read_csv(fl_data, header=None, delimiter=',', usecols=range(0, 15)).dropna()
		
		# elif LNG == 'jp':
		else:
			with open(flnames_en['names'], encoding='utf-8') as fl_names:
				names = pd.read_csv(fl_names, header=None, delimiter='|')
			
			with open(flnames_jp['names'], encoding='utf-8') as fl_names_jp:
				names_jp = pd.read_csv(fl_names_jp, header=None, delimiter=',')
			
			names = names.iloc[:, 0:1]
			names_jp = names_jp.iloc[:, 0:1]
			test = names.join(names_jp, how='outer', lsuffix='en', rsuffix='jp')
			gaps = test['0en'].isnull().values
			test = test.append(test[gaps], ignore_index=True)
			test['0en'][test['0en'].isnull()] = test['0jp'][test['0en'].isnull()]
			
			names = test['0en']
			
			with open(flnames_jp['data']) as fl_data:
				data = pd.read_csv(fl_data, header=None, delimiter=',', usecols=range(0, 15)).dropna()
			data = data.append(data[gaps], ignore_index=True)
		
		# Removes unused combos
		data = data[data[1] != -1]
		
		# Select combo names and relevant data
		data = data.iloc[:, -3:-1]
		
		data = data.astype(int, errors='ignore')
		# Merge the two [apparently by using 'inner' it removes the unused combos]
		tcmb = pd.concat([names, data], axis=1, join='inner')
		
		tcmb.reset_index(inplace=True, drop=True)
		tcmb.columns = schema_main[1:]
		
		return tcmb
	
	def get_names_effects_table(tc: DataFrame, teff: DataFrame) -> DataFrame:
		tcmb = tc.copy()
		tcmb['combo_effect_ID'] = tcmb['combo_effect_ID'].apply(lambda x: teff.iat[int(x), 0])
		tcmb['combo_size_ID'] = tcmb['combo_size_ID'].apply(lambda x: sizes[x])
		tcmb['combo_effect_ID'] = tcmb['combo_effect_ID'] + tcmb['combo_size_ID']
		
		tcmb = tcmb.iloc[:, 0:2]
		tcmb.columns = schema_CBmain
		
		return tcmb
	
	def get_units_in_combo_table(tunt: DataFrame, tcmb: DataFrame) -> DataFrame:
		final = tunt.copy()
		
		finaler = final['cat_1'].to_frame()
		
		cols = ['required_id']
		finaler.columns = cols
		
		finaler['combo_name'] = finaler.index
		finaler = finaler[['combo_name', 'required_id']]
		
		# Finaler is an accumulator which splits final from 5x1 to 1x5 basically
		
		final[5] = final.index
		
		# Thiccens the DataFrame
		for i in range(1, 5):
			f = final.iloc[:, [5, i]]
			f.columns = ['combo_name', 'required_id']
			finaler = pd.concat([finaler, f], axis=0)
		
		finaler = finaler[finaler['required_id'] >= 0]
		
		# Replaces combo IDs with their respective names
		finaler['combo_name'] = finaler['combo_name'].apply(lambda x: tcmb.iat[x, 0])
		finaler['accepted_id'] = finaler['required_id']
		
		finalest = pd.DataFrame(columns=['combo_name', 'required_id', 'accepted_id'])
		
		# Adds rows for forms
		for index, row in finaler.iterrows():
			n = 3 - int(row['accepted_id']) % 3
			for i in range(n):
				r = row.copy()
				r['accepted_id'] += i
				finalest = finalest.append(r)
		
		return finalest

	print("Started extracting combos")
	table_sizes = get_combo_sizes_table()
	table_effects = get_combo_effects_table()
	table_combos = get_combo_table()
	table_units = get_combo_units_table()
	
	if not LOADMODE:
		if LNG == 'jp':
			invert_imp()
		
		table_sizes.to_sql('combo_sizes', conn2, if_exists='replace', index=True, index_label=schema_sizes[0])
		table_effects.to_sql('combo_effects', conn2, if_exists='replace', index=True, index_label=schema_effects[0])
		
		table_units.to_sql('combo_units', conn2, if_exists='replace', index=True, index_label=schema_units[0])
		table_combos.to_sql('combos', conn2, if_exists='replace', index=True, index_label=schema_main[0])
		print("Waiting for user to update Combos intermediate table")
		
	if LOADMODE:
		table_combos = pd.read_sql('SELECT combo_name, combo_effect_ID, combo_size_ID FROM combos', conn2)
		table_units = pd.read_sql('SELECT cat_1,cat_2,cat_3,cat_4,cat_5 FROM combo_units', conn2)
		invert_imp()
	
	if CBMODE and not (LNG == 'jp' and not LOADMODE):
		table_names_eff = get_names_effects_table(table_combos, table_effects)
		table_in_combo = get_units_in_combo_table(table_units, table_combos)
		
		table_in_combo.to_sql('units_in_combo', conn, if_exists='replace', index=False)
		table_names_eff.to_sql('names_effects', conn, if_exists='replace', index=False)
		print('Finished extracting combos')
		
