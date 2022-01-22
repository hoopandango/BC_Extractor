import pandas as pd
import json

from .z_downloaders import Downloaders

with open('_config.json') as fl:
	config = json.load(fl)

enemydata = pd.read_csv(config['outputs']['enemies'], delimiter='\t', header=None, index_col=0)
stagedata = pd.read_csv(config['outputs']['substages'], delimiter='\t', header=None, index_col=0)
catdata = pd.read_csv(config['outputs']['units'], delimiter='\t', header=0, index_col=0)
combodata = pd.read_csv(config['outputs']['combos2'], delimiter='\t', header=0, index_col=0)
itemdata = pd.read_csv(config['outputs']['items'], delimiter='\t', header=0, index_col=0)
missiondata = pd.read_csv(config['outputs']['missions'], delimiter='\t', header=0, index_col=0)
saledata = pd.read_csv(config['outputs']['extras'], delimiter='\t', header=0, index_col=0)

forms = ['name_f', 'name_c', 'name_s']

class Readers:
	@staticmethod
	def getCat(ID: int, form: int) -> str:
		try:
			return catdata.loc[ID, forms[form]]
		except IndexError:
			return 'Invalid form'
		except KeyError:
			return 'Unknown'
		
	@staticmethod
	def getItem(ID: int) -> str:
		try:
			return itemdata.loc[ID, "name"]
		except KeyError:
			return 'Unknown'
	
	@staticmethod
	def getItemBySever(ID: int) -> str:
		try:
			item = itemdata.loc[itemdata["severID"] == ID, "name"]
			return item.to_list()[0]
		except IndexError:
			return 'Unknown'

	@staticmethod
	def getSaleBySever(ID: int) -> str:
		try:
			return saledata.loc[ID, "name"]
		except KeyError:
			return 'Unknown'

	@staticmethod
	def getEnemy(ID: int) -> str:
		try:
			return enemydata.loc[ID, 1]
		except KeyError:
			return 'Unknown'

	@staticmethod
	def getCombo(ID: int) -> str:
		try:
			return combodata.loc[ID, 1]
		except KeyError:
			return 'Unknown'
	
	@staticmethod
	def getMission(ID: int) -> str:
		try:
			return missiondata.loc[ID, 'mission_text']
		except KeyError:
			return 'Unknown'

	@staticmethod
	def getMap(ID: int) -> str:
		match ID:
			case 3000:
				return "EoC Ch.1"
			case 3001:
				return "EoC Ch.2"
			case 3002:
				return "EoC Ch.3"
		i = str(ID).zfill(6)
		try:
			return stagedata.loc[f"{i[0:3]}-{i[3:6]}", 2]
		except KeyError:
			return Downloaders.requestStage(ID, 'en')

	@staticmethod
	def getStage(ID: int) -> str:
		if (ID == 300147):
			ID = 300949
		elif (ID == 300247):
			ID = 300950
		elif (300300 > ID >= 300000):
			ID += 900
		
		i = str(ID).zfill(6)
		
		i1 = i[:-5].zfill(3)
		i2 = i[-5:-2]
		i3 = i[-2:].zfill(3)
		
		try:
			return f"{stagedata.loc[f'{i1}-{i2}-{i3}', 1]} [{stagedata.loc[f'{i1}-{i2}', 2]}]"
		except KeyError:
			return "Unknown"
	
	@classmethod
	def getStageOrMap(cls, ID: int) -> str:
		if (ID >= 100000): return cls.getStage(ID)
		else: return cls.getMap(ID)
