import string
from functools import lru_cache

import pandas as pd
import json

from .z_downloaders import Downloaders

with open('_config.json') as fl:
	config = json.load(fl)


forms = ['name_f', 'name_c', 'name_s']

class Readers:
	enemydata = pd.read_csv(config['outputs']['enemies'], delimiter='\t', header=None, index_col=0)
	stagedata = pd.read_csv(config['outputs']['substages'], delimiter='\t', header=None, index_col=0)
	stagesold = pd.read_csv(config['outputs']['stages'], delimiter='\t', header=0, index_col=0)
	catdata = pd.read_csv(config['outputs']['units'], delimiter='\t', header=0, index_col=0)
	combodata = pd.read_csv(config['outputs']['combos2'], delimiter='\t', header=0, index_col=0)
	itemdata = pd.read_csv(config['outputs']['items'], delimiter='\t', header=0, index_col=0)
	missiondata = pd.read_csv(config['outputs']['missions'], delimiter='\t', header=0, index_col=0)
	saledata = pd.read_csv(config['outputs']['extras'], delimiter='\t', header=0, index_col=0)
	
	@classmethod
	def reload(cls):
		cls.enemydata = pd.read_csv(config['outputs']['enemies'], delimiter='\t', header=None, index_col=0)
		cls.stagedata = pd.read_csv(config['outputs']['substages'], delimiter='\t', header=None, index_col=0)
		cls.stagesold = pd.read_csv(config['outputs']['stages'], delimiter='\t', header=0, index_col=0)
		cls.catdata = pd.read_csv(config['outputs']['units'], delimiter='\t', header=0, index_col=0)
		cls.combodata = pd.read_csv(config['outputs']['combos2'], delimiter='\t', header=0, index_col=0)
		cls.itemdata = pd.read_csv(config['outputs']['items'], delimiter='\t', header=0, index_col=0)
		cls.missiondata = pd.read_csv(config['outputs']['missions'], delimiter='\t', header=0, index_col=0)
		cls.saledata = pd.read_csv(config['outputs']['extras'], delimiter='\t', header=0, index_col=0)
	
	@classmethod
	@lru_cache
	def getCat(cls, ID: int, form: int) -> str:
		try:
			return cls.catdata.loc[ID, forms[form]]
		except IndexError:
			return 'Invalid form'
		except KeyError:
			return 'Unknown'
		
	@classmethod
	@lru_cache
	def getItem(cls, ID: int) -> str:
		try:
			return cls.itemdata.loc[ID, "name"]
		except KeyError:
			return 'Unknown'
	
	@classmethod
	@lru_cache
	def getItemBySever(cls, ID: int) -> str:
		try:
			item = cls.itemdata.loc[cls.itemdata["severID"] == ID, "name"]
			return item.to_list()[0]
		except IndexError:
			return 'Unknown'

	@classmethod
	def getSaleBySever(cls, ID: int) -> str:
		try:
			return cls.saledata.loc[ID, "name"]
		except KeyError:
			return 'Unknown'

	@classmethod
	@lru_cache
	def getEnemy(cls, ID: int) -> str:
		try:
			return cls.enemydata.loc[ID, 1]
		except KeyError:
			return 'Unknown'

	@classmethod
	@lru_cache
	def getCombo(cls, ID: int) -> str:
		try:
			return cls.combodata.loc[ID, "combo_name"]
		except KeyError:
			return 'Unknown'
	
	@classmethod
	@lru_cache
	def getMission(cls, ID: int) -> str:
		try:
			return cls.missiondata.loc[ID, 'mission_text']
		except KeyError:
			return 'Unknown'

	@classmethod
	@lru_cache
	def getMap(cls, ID: int, check_online: bool = True) -> str:
		def isEnglish(name: str)->bool:
			eng = len([0 for x in name if x in string.ascii_letters])
			full = len([0 for x in name if x.isalpha()])
			return full < 2*eng
		
		def lookup(store_jp: bool, default: str)->str:
			toret = Downloaders.requestStage(ID, 'en')  # online lookup
			if toret != "Unknown":  # request cleared
				if isEnglish(toret) or store_jp:  # desirable response
					Downloaders.stash_cache(ID, toret)  # copy to cache
				return toret  # return whatver you got here
			return default  # settle for the default value
				
		match ID:
			case 3000:
				return "EoC Ch.1"
			case 3001:
				return "EoC Ch.2"
			case 3002:
				return "EoC Ch.3"
		
		try:
			local = cls.stagesold.loc[ID, "name"]
			if isEnglish(local):  # cache hit - en
				return local
			else:  # cache hit-jp
				if check_online:
					return lookup(False, local)
				return local
		except KeyError:  # cache miss
			if check_online:
				return lookup(True, "Unknown")
			
		return ("Unknown")
		
	@classmethod
	@lru_cache
	def getStage(cls, ID: int) -> str:
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
			return f"{cls.stagedata.loc[f'{i1}-{i2}-{i3}', 1]} [{cls.stagedata.loc[f'{i1}-{i2}', 2]}]"
		except KeyError:
			return "Unknown"
	
	@classmethod
	def getStageOrMap(cls, ID: int, check_online=True) -> str:
		# Does not look up online if check misses
		if (ID >= 100000): return cls.getStage(ID)
		else: return cls.getMap(ID, check_online=check_online)
