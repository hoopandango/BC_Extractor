import pandas as pd
import sqlite3
from pandas.core.frame import DataFrame
from base import config, schemas

gaps = None
def extract():
	sizes = ['UP Sm', 'UP M', 'UP L', 'UP XL']
	schema = schemas["combos"]
	
	# Set true to save DB in CatBot format
	CBMODE = config['setup']['combos']['catbotmode']
	
	schema_main = schema['regular']['main']
	schema_units = schema['regular']['units']
	schema_effects = schema['regular']['effects']
	schema_sizes = schema['regular']['sizes']
	schema_CBmain = schema['catbot']['main']
	
	flnames_en = config['inputs']['en']['combos']
	flnames_jp = config['inputs']['jp']['combos']
	
	output = config['outputs']['combos']
	interm = config['intermediates']['combos']
	
	def get_combo_sizes_table() -> DataFrame:
		return pd.read_csv(flnames_en["sizes"], header=None, delimiter='|', names=schema_sizes[1:], usecols=[0])
	
	def get_combo_effects_table() -> DataFrame:
		return pd.read_csv(flnames_en["effects"], header=None, delimiter='|', names=schema_effects[1:], usecols=[0])
	
	def get_combo_units_table() -> DataFrame:
		df = pd.read_csv(flnames_jp['data'], header=None, delimiter=',', usecols=range(0, 14), skipfooter=1, engine='python').dropna()
		
		df = df[df[1] != -1]  # filter unused combos
		tunt = pd.DataFrame(columns=schema_units[1:])
		
		for i in range(1, 6):
			# 2i => Base ID, 2i+1 => Form number | 0,1,12,13 are metadata,
			tunt.iloc[:, i-1] = 3 * df[2 * i] + df[2 * i + 1]  # Converts PONOS ID to CatBot ID
		
		tunt = tunt.applymap(lambda x: max(x, -1))  # Converts dummy slots to -1
		return tunt
	
	def get_combo_table() -> DataFrame:
		names_en = pd.read_csv(flnames_en['names'], header=None, delimiter='|', usecols=[0])
		names_jp = pd.read_csv(flnames_jp['names'], header=None, delimiter=',', usecols=[0])

		names = names_jp.copy()
		temp = names_en.dropna()
		names.loc[temp.index] = temp
		names = pd.concat([names, names[names[0] == names_jp[0]]], axis=0)
		
		# footer row has garbage value in data table
		data = pd.read_csv(flnames_jp['data'], header=None, delimiter=',', usecols=range(0, 14), skipfooter=1, engine='python')
		
		# Removes unused combos
		data = data[data[1] != -1]
		data = data.iloc[:, 12:]
		
		tcmb = names.join(data, how='inner')
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
		tcmb = tcmb.drop(columns=['combo_effect_ID','combo_size_ID'])
		base = tcmb.join(tunt)
		base["required_id"] = base[[f"cat_{i}" for i in range(1, 6)]].values.tolist()
		base = base.loc[:, ["combo_name", "required_id"]]\
			.explode("required_id")
		
		# filter out empty unit slots
		base = base[base['required_id'] >= 0]
		base['accepted_id'] = base.loc[:, ['required_id']]
		base['accepted_id'] = base['accepted_id'].apply(
			lambda X: [X+i for i in range(0, 3 - X % 3)]
		)
		base = base.explode('accepted_id')
		return base
	
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
	
	print("Started extracting combos")
	table_sizes = get_combo_sizes_table()
	table_effects = get_combo_effects_table()
	table_combos = get_combo_table()
	table_units = get_combo_units_table()
	
	table_sizes.to_sql('combo_sizes', conn2, if_exists='replace', index=True, index_label=schema_sizes[0])
	table_effects.to_sql('combo_effects', conn2, if_exists='replace', index=True, index_label=schema_effects[0])
	
	table_units.to_sql('combo_units', conn2, if_exists='replace', index=True, index_label=schema_units[0])
	table_combos.to_sql('combos', conn2, if_exists='replace', index=True, index_label=schema_main[0])
	
	if CBMODE:
		input("Waiting for user to update Combos intermediate table")
		
		table_combos = pd.read_sql('SELECT ID,combo_name, combo_effect_ID, combo_size_ID FROM combos', conn2, index_col='ID')
		table_units = pd.read_sql('SELECT ID,cat_1,cat_2,cat_3,cat_4,cat_5 FROM combo_units', conn2, index_col='ID')
		table_names_eff = get_names_effects_table(table_combos, table_effects)
		table_in_combo = get_units_in_combo_table(table_units, table_combos)
		
		table_in_combo.to_sql('units_in_combo', conn, if_exists='replace', index=False)
		table_names_eff.to_sql('names_effects', conn, if_exists='replace', index=False)
		
	print('Finished extracting combos')
	
if __name__ == "__main__":
	extract()
