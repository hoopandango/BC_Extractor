import pandas as pd
import sqlite3
from src_extractors.base import config, schemas
from src_backend.local_readers import Readers

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

	def updateTalentsTable() -> pd.DataFrame:
		df = pd.read_csv(flnames['main'])
		final = pd.DataFrame(columns=CatBotColumns)
		
		# Break table into 6 tables and merge them
		for i in range(6):
			s = df.iloc[:, [0] + list(range(l * i + 2, l * (i + 1) + 1))]
			s.columns = CatBotColumns
			final = pd.concat([final, s], axis=0)
		
		final.sort_values(by=['unit_id'], inplace=True,
											kind='mergesort')  # Sort table into readable order, needs to be stable
		
		final = final[final["description"] != 0]
		final.index = list(range(len(final)))  # Reset indices
		
		final.to_sql('talents', conn, if_exists='replace', index=True)  # Replace old table with new one
		return final

	def updateLevelsTable() -> pd.DataFrame:
		df = pd.read_csv(flnames['levels'], index_col=False)
		df.to_sql('curves', conn, if_exists='replace', index=True)
		return df

	def updateDescriptionsTable() -> pd.DataFrame:
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
		return df_jp
	
	def getcostoftalent(curve, level):
		level = max(level, 1)  # PONOS is stupid and makes max level 0 sometimes
		return int(sum(curve[1:1 + level]))
	
	def parsetalent(tln):
		message = ""
		
		nfirst_param = tln['min_first_parameter']
		nsecond_param = tln['min_second_parameter']
		nthird_param = tln['min_third_parameter']
		nfourth_param = tln['min_fourth_parameter']
		
		xfirst_param = tln['max_first_parameter']
		xsecond_param = tln['max_second_parameter']
		
		talent_to_apply = tln['description']
		
		if talent_to_apply == 1:  # weaken
			message = f"Gains a {int(nfirst_param)}% chance to weaken targeted enemies to {int(100 - nthird_param)}%, with duration increasing from {int(nsecond_param)}f to {int(xsecond_param)}f"
		elif talent_to_apply == 2:  # freeze
			message = f"Gains a {int(nfirst_param)}% chance to freeze targeted enemies, with duration increasing from {int(nsecond_param)}f to {int(xsecond_param)}f"
		elif talent_to_apply == 3:  # slow
			message = f"Gains a {int(nfirst_param)}% chance to slow targeted enemies, with duration increasing from {int(nsecond_param)}f to {int(xsecond_param)}f"
		elif talent_to_apply == 4:  # target only
			message = "Gains the Target Only ability against its target traits"
		elif talent_to_apply == 5:  # strong
			message = "Gains the Strong ability against its target traits"
		elif talent_to_apply == 6:  # resist
			message = "Gains the Resistant ability against its target traits"
		elif talent_to_apply == 7:  # massive damage
			message = "Gains the Massive ability against its target traits"
		elif talent_to_apply == 8:  # knockback
			message = f"Gains a chance to knock back targeted enemies, increasing from {int(nfirst_param)}% to {int(xfirst_param)}%"
		elif talent_to_apply == 9:  # warp (unused)
			pass
		elif talent_to_apply == 10:  # strengthen
			message = f"Gains an attack boost at {int(100 - nfirst_param)}% HP, increasing from {int(nsecond_param)}% to {int(xsecond_param)}%"
		elif talent_to_apply == 11:  # survive
			message = f"Gains a chance to survive a Lethal Strike, increasing from {int(nfirst_param)}% to {int(xfirst_param)}%"
		elif talent_to_apply == 12:  # base destroyer
			message = "Gains the Base Destroyer ability"
		elif talent_to_apply == 13:  # critical (unused)
			pass
		elif talent_to_apply == 14:  # zombie killer
			message = "Gains the Zombie Killer ability"
		elif talent_to_apply == 15:  # barrier breaker
			message = f"Gains a chance to Break Barriers, increasing from {int(nfirst_param)}% to {int(xfirst_param)}%"
		elif talent_to_apply == 16:  # double cash
			message = "Gains the Double Bounty ability"
		elif talent_to_apply == 17:  # wave attack
			message = f"Gains a chance to make a level {int(xsecond_param)} wave, increasing from {int(nfirst_param)}% to {int(xfirst_param)}%"
		elif talent_to_apply == 18:  # resists weaken
			message = f"Reduces duration of Weaken, increasing from {int(nfirst_param)}% to {int(xfirst_param)}%"
		elif talent_to_apply == 19:  # resists freeze
			message = f"Reduces duration of Freeze, increasing from {int(nfirst_param)}% to {int(xfirst_param)}%"
		elif talent_to_apply == 20:  # resists slow
			message = f"Reduces duration of Slow, increasing from {int(nfirst_param)}% to {int(xfirst_param)}%"
		elif talent_to_apply == 21:  # resists knockback
			message = f"Reduces distance of Knockback, increasing from {int(nfirst_param)}% to {int(xfirst_param)}%"
		elif talent_to_apply == 22:  # resists waves
			message = f"Reduces damage of Curse, increasing from {int(nfirst_param)}% to {int(xfirst_param)}%"
		elif talent_to_apply == 23:  # wave immune (unused)
			pass
		elif talent_to_apply == 24:  # warp block (unused)
			pass
		elif talent_to_apply == 25:  # curse immunity
			message = "Gains immunity to Curse"
		elif talent_to_apply == 26:  # resist curse
			message = f"Reduces duration of Curse, increasing from {int(nfirst_param)}% upto {int(xfirst_param)}%"
		elif talent_to_apply == 27:  # hp up
			message = f"Increases HP by {int(nfirst_param)}% per level upto {int(xfirst_param)}%"
		elif talent_to_apply == 28:  # atk up
			message = f"Increases Damage by {int(nfirst_param)}% per level upto {int(xfirst_param)}%"
		elif talent_to_apply == 29:  # speed up
			message = f"Increases Speed by {int(nfirst_param)} per level upto {int(xfirst_param)}"
		elif talent_to_apply == 30:  # knockback chance up (unused)
			pass
		elif talent_to_apply == 31:  # cost down
			message = f"Reduces Cost of unit, increasing from {int(nfirst_param)} to {int(xfirst_param)}"
		elif talent_to_apply == 32:  # recharge down
			message = f"Reduces Cooldown of unit, increasing from {int(nfirst_param)}f to {int(xfirst_param)}f"
		elif talent_to_apply == 33:  # target red
			message = "Gains Red as a target trait"
		elif talent_to_apply == 34:  # target floating
			message = "Gains Floating as a target trait"
		elif talent_to_apply == 35:  # target black
			message = "Gains Black as a target trait"
		elif talent_to_apply == 36:  # target metal
			message = "Gains Metal as a target trait"
		elif talent_to_apply == 37:  # target angel
			message = "Gains Angel as a target trait"
		elif talent_to_apply == 38:  # target alien
			message = "Gains Alien as a target trait"
		elif talent_to_apply == 39:  # target zombies
			message = "Gains Zombie as a target trait"
		elif talent_to_apply == 40:  # target relic
			message = "Gains Relic as a target trait"
		elif talent_to_apply == 41:  # target traitless
			message = "Gains White as a target trait"
		elif talent_to_apply == 42:  # weaken duration up
			message = f"Increases duration of Weaken, from {nsecond_param}f to {xsecond_param}f"
		elif talent_to_apply == 43:  # freeze duration up
			message = f"Increases duration of Freeze, from {nsecond_param}f to {xsecond_param}f"
		elif talent_to_apply == 44:  # slow duration up
			message = f"Increases duration of Slow, from {nsecond_param}f to {xsecond_param}f"
		elif talent_to_apply == 45:  # knockback chance up
			message = f"Increases distance of Knockback, by {nfirst_param} to {xfirst_param} units"
		elif talent_to_apply == 46:  # strengthen power up
			message = f"Increases amount of Strengthen, by {nsecond_param}% till {xsecond_param}%"
		elif talent_to_apply == 47:  # survive chance
			message = f"Increases chance of Survivor by {nfirst_param} upto {xfirst_param}"
		elif talent_to_apply == 48:  # critical chance
			message = f"Increases chance of a Critical Attack by {nfirst_param} upto {xfirst_param}"
		elif talent_to_apply == 49:  # barrier breaker chance
			message = f"Increases chance of breaking enemy barrier by {nfirst_param} upto {xfirst_param}"
		elif talent_to_apply == 50:  # wave chance (unused)
			pass
		elif talent_to_apply == 51:  # warp duration (unused)
			pass
		elif talent_to_apply == 52:  # critical
			message = f"Gains a {int(nfirst_param)}% chance to deal a Critical Attack"
		elif talent_to_apply == 53:  # weaken immune
			message = "Gains immunity to Weaken"
		elif talent_to_apply == 54:  # freeze immune
			message = "Gains immunity to Freeze"
		elif talent_to_apply == 55:  # slow immune
			message = "Gains immunity to Slow"
		elif talent_to_apply == 56:  # knockback immune
			message = "Gains immunity to Knockback"
		elif talent_to_apply == 57:  # wave immune
			message = "Gains immunity to Waves"
		elif talent_to_apply == 58:  # warp block
			message = "Gains immunity to Warp"
		elif talent_to_apply == 59:  # savage blow
			message = f"Gains a chance to deal a Savage Blow (does {round(1 + nsecond_param / 100, 2)}x damage), increasing from {int(nfirst_param)}% to {int(xfirst_param)}%"
		elif talent_to_apply == 60:  # dodge
			message = f"Gains a {int(nfirst_param)}% chance to dodge attacks, with duration increasing from {int(nsecond_param)}f to {int(xsecond_param)}f"
		elif talent_to_apply == 61:  # savage blow chance (unused)
			pass
		elif talent_to_apply == 62:  # dodge duration (unused)
			pass
		elif talent_to_apply == 63:  # slow chance
			message = f"Increases slow chance by {int(nfirst_param)}% per level upto {int(xfirst_param)}%"
		elif talent_to_apply == 64:  # resist toxic
			message = f"Reduces damage from Toxic by {int(nfirst_param)}% per level upto {int(xfirst_param)}%"
		elif talent_to_apply == 65:  # toxic immune
			message = "Gains immunity to Toxic"
		elif talent_to_apply == 66:  # resist surge
			message = f"Reduces damage from Surge by {int(nfirst_param)}% per level upto {int(xfirst_param)}%"
		elif talent_to_apply == 67:  # surge immune
			message = "Gains immunity to Surge"
		elif talent_to_apply == 68:  # surge attack
			message = f"Gains a chance to make a level {int(nsecond_param)} Surge between {int(nthird_param / 4)}~{int(nthird_param / 4 + nfourth_param / 4)} range, increasing from {int(nfirst_param)}% to {int(xfirst_param)}%"
		elif talent_to_apply == 69:  # slow relic
			message = message = f"Gains a {int(nfirst_param)}% chance to slow Relic enemies, with duration increasing from {int(nsecond_param)}f to {int(xsecond_param)}f"
		elif talent_to_apply == 70:  # weaken relic
			message = f"Gains a {int(nfirst_param)}% chance to weaken Relic enemies to {int(100 - nthird_param)}%, with duration increasing from {int(nsecond_param)}f to {int(xsecond_param)}f"
		elif talent_to_apply == 71:  # weaken alien
			message = f"Gains a {int(nfirst_param)}% chance to weaken Alien enemies to {int(100 - nthird_param)}%, with duration increasing from {int(nsecond_param)}f to {int(xsecond_param)}f"
		elif talent_to_apply == 72:  # slow metal
			message = f"Gains a {int(nfirst_param)}% chance to slow Metal enemies, with duration increasing from {int(nsecond_param)}f to {int(xsecond_param)}f"
		elif talent_to_apply == 73:  # knockback zombies
			message = f"Gains a chance to knock back Zombie enemies, increasing from {int(nfirst_param)}% to {int(xfirst_param)}%"
		elif talent_to_apply == 74:  # freeze chance up
			message = f"Increases freeze chance by {int(nfirst_param)}% per level upto {int(xfirst_param)}%"
		elif talent_to_apply == 75:  # knockback alien
			message = f"Gains a chance to knock back Alien enemies, increasing from {int(nfirst_param)}% to {int(xfirst_param)}%"
		elif talent_to_apply == 76:  # freeze metal
			message = f"Gains a {int(nfirst_param)}% chance to freeze Metal enemies, with duration increasing from {int(nsecond_param)}f to {int(xsecond_param)}f"
		elif talent_to_apply == 77:  # target aku
			message = f"Gains Aku as a target trait"
		elif talent_to_apply == 78:  # shield piercing
			message = f"Gains ability to pierce Aku Shields, with probability increasing from {int(nfirst_param)}% to {int(xfirst_param)}%"
		elif talent_to_apply == 79:  # soul strike
			message = f"Gains Soul Strike ability"
		elif talent_to_apply == 80:  # curse duration
			message = f"Increasing curse duration from {int(nsecond_param)}f to {int(xsecond_param)}f"
		return message
	
	talents = updateTalentsTable()
	descs = updateDescriptionsTable()
	levels = updateLevelsTable().to_dict('tight')['data']
	
	prev = ''
	buf = ""
	for talent in talents.to_dict('records'):
		cat = Readers.getCat(talent['unit_id'], 2)
		if prev != cat:
			buf += f'\n{cat}\n'
			prev = cat
		buf += f"{descs.loc[talent['description'], 'description_text']}: {parsetalent(talent)} ({getcostoftalent(levels[talent['cost_curve'] - 1], talent['max_level'])} NP)\n"
	
	buf = buf[1:]  # removes the first empty line
	with open(config['outputs']['talents2'], mode='w', encoding='utf-8') as fl:
		fl.write(buf)
		
	print("Finished extracting talents")
	
if __name__ == '__main__':
	extract()
	