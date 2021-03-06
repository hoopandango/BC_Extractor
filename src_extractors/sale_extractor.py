import pandas as pd
from src_extractors.base import config, schemas

def extract():
	# region setup
	schema = schemas["sales"]

	flnames_jp = config['inputs']['jp']['sales']
	flnames_en = config['inputs']['en']['sales']
	fl_out = config['outputs']['sales']

	# endregion

	def load_item_pack():
		with open(flnames_jp["itempack"]) as fl1:
			df = pd.read_csv(fl1, delimiter='\t')
		
		df = df[(900 > df.loc[:, 'server']) & (df.loc[:, 'server'] > 799)]  # & (df.loc[:,'enable'] > 0)]
		df = df.iloc[:, [0, 3]]
		
		df.columns = schema["itempack"]
		df.set_index('ID', inplace=True)
		return df

	def load_localisable():
		with open(flnames_en["localisable"], encoding='utf-8') as fl1:
			df_en = pd.read_csv(fl1, header=None, delimiter='\t')
		df_en = df_en[df_en[0].str.startswith('item_pack_name_')]
		df_en[0] = df_en[0].str.replace('item_pack_name_', '').astype(int)
		df_en.columns = schema["localisable"]
		df_en.set_index("ID", inplace=True)
		
		with open(flnames_jp["localisable"], encoding='utf-8') as fl1:
			df_jp = pd.read_csv(fl1, header=None, delimiter='\t')
		df_jp = df_jp[df_jp[0].str.startswith('item_pack_name_')]
		df_jp[0] = df_jp[0].str.replace('item_pack_name_', '').astype(int)
		df_jp.columns = schema["localisable"]
		df_jp.set_index("ID", inplace=True)
		
		torep = set(df_jp.index).intersection(set(df_en.index))
		df_jp.loc[torep, :] = df_en.loc[torep, :]
		df = df_jp
		df = df.dropna(axis='rows')
		return df

	print("Started extracting sales")
	# Ungrouped Sales
	dt = pd.concat([load_item_pack(), load_localisable()], axis=1, join='inner')

	# Grouped Sales
	dt = dt.groupby('severID').agg(lambda x: x.tolist())
	dt = dt.applymap(lambda x: '|'.join(x))

	dt.to_csv(fl_out, sep='\t')
	print("Finished extracting sales")
