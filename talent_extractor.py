import pandas as pd
import sqlite3
from utils import unpad_file
import json

# region setup
with open('_config.json') as fl:
	config = json.load(fl)

with open('_schemas.json') as fl:
	schemas = json.load(fl)['talents']

LNG = config['setup']['LNG']

CatBotColumns = schemas['main']
l = len(CatBotColumns)

flnames = config['inputs']['jp']['talents']
flnames_en = config['inputs']['en']['talents']

for fl in flnames:
	unpad_file(flnames[fl])

for fl in flnames_en:
	unpad_file(flnames_en[fl])

try:
	conn = sqlite3.connect(config['outputs']['talents'])
	print("Database for talents found.")
except sqlite3.OperationalError:  # database not found
  print("Database for talents not found.")
# endregion


def updateTalentsTable():
	df = pd.read_csv(flnames['main'])

	df.dropna(inplace = True)  # Removes padding row and any other problematic rows 

	df = df.astype('int32')  # Turns floats into ints after all the problematic rows are gone

	final = pd.DataFrame(columns = CatBotColumns)

	# Break table into 5 tables and merge them
	for i in range(5):
		s = df.iloc[:,[0]+list(range(l*i+2,l*(i+1)+1))]
		s.columns = CatBotColumns
		final = final.append(s)

	final.sort_values(by = ['unit_id'], inplace = True, kind = 'mergesort')  # Sort table into readable order, needs to be stable

	final.index = list(range(len(final)))  # Reset indices
	
	final.to_sql('talents', conn, if_exists = 'replace', index = True)  # Replace old table with new one
	print('Talents table updated')

def updateLevelsTable():
	df = pd.read_csv(flnames['levels'],index_col=False)

	df = df.astype(pd.Int64Dtype())

	df.to_sql('curves', conn, if_exists = 'replace', index = True)

	print('Levelling curves table updated')

def updateDescriptionsTable():
	df_jp = pd.read_csv(flnames['descriptions'],index_col='textID')
	df_en = pd.read_csv(flnames_en['descriptions'],index_col='textID',delimiter='|')

	df_jp.rename_axis(schemas['descriptions'][0], inplace = True)
	df_jp.columns = schemas['descriptions'][1:]

	df_en.rename_axis(schemas['descriptions'][0], inplace = True)
	df_en.columns = schemas['descriptions'][1:]

	# existing > en > jp
	existing = pd.read_sql('SELECT * FROM talents_explanation',conn,'description_id')
	df_jp["description_text"][df_en.index] = df_en["description_text"][:]
	df_jp["description_text"][existing.index] = existing["description_text"][:]

	
	df_jp.to_sql('talents_explanation', conn, if_exists = 'replace', index = True)

	print('Talent Descriptions table updated')

updateTalentsTable()
updateLevelsTable()
updateDescriptionsTable()

input()