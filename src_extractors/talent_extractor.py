import pandas as pd
import sqlite3
from base import config, schemas

def extract():
	schema = schemas['talents']
	CatBotColumns = schema['main']
	l = len(CatBotColumns)

	flnames = config['inputs']['jp']['talents']
	flnames_en = config['inputs']['en']['talents']

	try:
		conn = sqlite3.connect(config['outputs']['talents'])
	except sqlite3.OperationalError:  # database not found
		print("Database for talents not found.")
		return

	def updateTalentsTable():
		df = pd.read_csv(flnames['main'])
		final = pd.DataFrame(columns=CatBotColumns)
		
		# Break table into 6 tables and merge them
		for i in range(6):
			s = df.iloc[:, [0] + list(range(l * i + 2, l * (i + 1) + 1))]
			s.columns = CatBotColumns
			final = final.concat(s, axis=0)
		
		final.sort_values(by=['unit_id'], inplace=True,
											kind='mergesort')  # Sort table into readable order, needs to be stable
		
		final = final[final["description"] != 0]
		final.index = list(range(len(final)))  # Reset indices
		
		final.to_sql('talents', conn, if_exists='replace', index=True)  # Replace old table with new one

	def updateLevelsTable():
		df = pd.read_csv(flnames['levels'], index_col=False)
		df.to_sql('curves', conn, if_exists='replace', index=True)

	def updateDescriptionsTable():
		df_jp = pd.read_csv(flnames['descriptions'], index_col='textID')
		df_en = pd.read_csv(flnames_en['descriptions'], index_col='textID', delimiter='|')
		
		df_jp.rename_axis(schema['descriptions'][0], inplace=True)
		df_jp.columns = schema['descriptions'][1:]
		
		df_en.rename_axis(schema['descriptions'][0], inplace=True)
		df_en.columns = schema['descriptions'][1:]
		
		# existing > en > jp
		existing = pd.read_sql('SELECT * FROM talents_explanation', conn, 'description_id')
		df_jp["description_text"][df_en.index] = df_en["description_text"][:]
		df_jp["description_text"][existing.index] = existing["description_text"][:]
		
		df_jp.to_sql('talents_explanation', conn, if_exists='replace', index=True)

	updateTalentsTable()
	updateDescriptionsTable()
	updateLevelsTable()
	print("Finished extracting talents")
	