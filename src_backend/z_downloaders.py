import pandas as pd
import requests
import regex as re
import atexit
import json
from functools import lru_cache

with open('_config.json') as fl:
	config = json.load(fl)
	
@atexit.register
def unload_changes():
	inp = pd.read_csv(config['outputs']['stages'], sep='\t', index_col=0)
	buf_entries = pd.DataFrame.from_dict(Downloaders.buffer, orient='index')
	toput = pd.concat([inp, buf_entries], axis=0)
	toput = toput[~toput.index.duplicated(keep='last')]  # retains last one in final
	toput.to_csv(config['outputs']['stages'], sep='\t')
	
class Downloaders:
	prefixes = {1: 'S', 2: 'C', 6: 'T', 7: 'V', 11: 'R', 12: 'M', 13: 'NA', 14: 'B', 24: 'A', 25: 'H', 27: 'CA'}
	
	buffer = {}
	
	@classmethod
	def stash_cache(cls, ID: int, name: str):
		cls.buffer[ID] = name
	
	@classmethod
	@lru_cache
	def requestStage(cls, ID: int, lng: str):
		# print(ID)
		prefix = "https://ponos.s3.dualstack.ap-northeast-1.amazonaws.com/information/appli/battlecats/stage/"
		pre = Downloaders.prefixes.get(ID // 1000)
		if pre is None:
			return "Unknown"
		file = '%s%03d.html' % (pre, ID % 1000)
		for country in [lng + '/', ""]:
			try:
				r = requests.get(prefix + country + file)
			except requests.exceptions.RequestException as e:
				return f'Request Failed - {e}'
			c = r.content
			if b"<Code>AccessDenied</Code>" not in c and b'<h2><span' not in c and r.status_code != 404:
				try:
					level = c.split(b'<h2>')[1].split(b"<span")[0].decode('utf-8')
					return level
				except IndexError:
					pass
		return "Unknown"
	
	@staticmethod
	@lru_cache
	def requestGatya(ID: int, lng: str, cat: str = 'R') -> str:
		prefix = "https://ponos.s3.dualstack.ap-northeast-1.amazonaws.com/information/appli/battlecats/gacha/"
		if lng != 'jp':
			l = lng + '/'
		else:
			l = ''
		
		if (cat == 'N' or cat == 'Cat Capsule'):
			file = 'normal/%sN%03d.html' % (l, ID)
		elif (cat == 'E' or cat == 'Event Capsule'):
			file = 'event/%sE%03d.html' % (l, ID)
		else:
			file = 'rare/%sR%03d.html' % (l, ID)
		
		try:
			r = requests.get(prefix + file)
		except requests.exceptions.RequestException as e:
			if lng != 'jp':
				return Downloaders.requestGatya(ID, 'jp', cat)
			return f'Request Failed - {e}'
		c = r.content
		if b"<Code>AccessDenied</Code>" not in c and b'<h2><span' not in c and b'NoSuchKey' not in c:
			try:
				title = re.search(b'<h2>(.*)</h2>', c).group(1)
				title = re.sub(b'<span.*?</span>', b'', title, flags=re.DOTALL).decode('utf-8')
				return title
			except IndexError:
				pass
		return f"Unknown"
