import requests
import regex as re


class Downloaders:
	#TODO: 9 = missions, 18 = slots, 19 = talking cat rewards
	prefixes = {0:'N', 1:'S', 2:'C', 6:'T', 7:'V', 11:'R', 12:'M', 13:'NA', 14:'B', 24:'A', 25:'H', 27:'A'}
	@staticmethod
	def requestStage(ID:int, lng:str):
		prefix = "https://ponos.s3.dualstack.ap-northeast-1.amazonaws.com/information/appli/battlecats/stage/"
		pre = Downloaders.prefixes.get(ID // 1000)
		if pre == None:
			return "Unknown"
		file = '%s%03d.html' % (pre, ID % 1000)
		level = ""
		for country in [lng+'/',""]:
			try:
				r = requests.get(prefix+country+file)
			except requests.exceptions.RequestException as e:
				return f'Request Failed - {e}'
			c = r.content
			if b"<Code>AccessDenied</Code>" not in c and b'<h2><span' not in c:
				try:
					level = c.split(b'<h2>')[1].split(b"<span")[0].decode('utf-8')
					return level
				except IndexError: pass
		return "Unknown"

	@staticmethod
	def requestGatya(ID:int, lng:str, cat:str = 'R') -> str:
		prefix = "http://ponos.s3.dualstack.ap-northeast-1.amazonaws.com/information/appli/battlecats/gacha/"
		if lng != 'jp':
			l = lng+'/'
		else:
			l = ''

		if(cat == 'N'):
			file = 'normal/%sN%03d.html'%(l,ID)
		elif(cat == 'E'):
			file = 'event/%sE%03d.html'%(l,ID)
		else:
			file = 'rare/%sR%03d.html'%(l,ID)

		try:
			r = requests.get(prefix+file)
		except requests.exceptions.RequestException as e:
			if lng != 'jp':
				return Downloaders.requestGatya(ID,'jp',cat)
			return f'Request Failed - {e}'
		c = r.content
		if b"<Code>AccessDenied</Code>" not in c and b'<h2><span' not in c and b'NoSuchKey' not in c:
			try:
				title = re.search(b'<h2>(.*)</h2>', c).group(1)
				title = re.sub(b'<span.*?</span>', '', title, flags=re.DOTALL).decode('utf-8')
				return title
			except IndexError: pass
		return f"Unknown"